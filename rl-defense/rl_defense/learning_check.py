"""Does training change behaviour and outcomes? Trained vs untrained vs baselines.

    python -m rl_defense.learning_check --steps 150000 --seeds 0 1 2 --out results/learning-check

For each training seed this trains a Double DQN on the TRAINING configs, then runs five
policies on the HELD-OUT eval configs with the same episode seeds:

- ``ddqn_trained``   : the checkpoint just written, reloaded from disk (greedy)
- ``ddqn_untrained`` : the same architecture and init seed with zero gradient updates (greedy)
- ``random``         : uniform over valid actions
- ``noop``           : never acts
- ``threshold_rules``: rules tuned on the training configs only

The untrained network is the control the protocol-17 evaluation does not have: if training
did nothing, ``ddqn_trained`` and ``ddqn_untrained`` would act and score the same. The
report states what was measured, including where the trained policy is worse.

This is a learning check, not a protocol-17 evaluation: fewer steps and seeds, and no
selection. It never touches a real system; every number is simulation output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

from rl_defense.agents.ddqn import DDQNAgent, DDQNConfig
from rl_defense.baselines import (
    NoopPolicy,
    RandomValidPolicy,
    ThresholdRulesPolicy,
    tune_threshold_rules,
)
from rl_defense.baselines.policies import Policy, ThresholdParams
from rl_defense.checkpoint import git_sha, load_checkpoint
from rl_defense.envs import DefenseSimEnv, default_config_paths, load_configs
from rl_defense.envs.config import ScenarioConfig
from rl_defense.envs.defense_sim import N_ACTIONS, OBS_DIM
from rl_defense.evaluate import CAVEAT, bootstrap_ci, run_episode
from rl_defense.train import train

# lr and n-step from the protocol-v1 candidate; schedule shortened for a short run.
DEFAULT_CONFIG = DDQNConfig(lr=3e-4, n_step=3, eps_decay_steps=50_000)
DEFAULT_ADVERSARY_SCALE = (0.5, 2.5)
EPISODE_SEED_START = 1000  # the protocol's eval seeds
REPORTED = ("return", "compromise_rate", "false_disruption_rate", "service_uptime")
POLICIES = ("ddqn_trained", "ddqn_untrained", "random", "noop", "threshold_rules")


class GreedyAgentPolicy:
    def __init__(self, agent: DDQNAgent, name: str) -> None:
        self.agent, self.name = agent, name

    def reset(self, seed: int) -> None:
        pass

    def act(self, obs: np.ndarray, mask: np.ndarray) -> int:
        return self.agent.greedy_action(obs, mask)


def untrained_agent(config: DDQNConfig, seed: int) -> DDQNAgent:
    """Same constructor call as ``train`` makes, before any update."""
    return DDQNAgent(OBS_DIM, N_ACTIONS, config, seed=seed)


def param_distance(a: DDQNAgent, b: DDQNAgent) -> float:
    with torch.no_grad():
        return float(
            sum(
                (p - q).abs().sum()
                for p, q in zip(a.online.parameters(), b.online.parameters(), strict=True)
            )
        )


def action_agreement(
    a: DDQNAgent, b: DDQNAgent, eval_configs: list[ScenarioConfig], episodes: range
) -> float:
    """Share of states (visited by a random policy) where both greedy policies pick the same action."""
    same = total = 0
    walker = RandomValidPolicy(seed=0)
    for cfg in eval_configs:
        env = DefenseSimEnv(cfg)
        for ep_seed in episodes:
            obs, info = env.reset(seed=ep_seed)
            walker.reset(ep_seed)
            done = False
            while not done:
                mask = info["action_mask"]
                same += int(a.greedy_action(obs, mask) == b.greedy_action(obs, mask))
                total += 1
                obs, _, term, trunc, info = env.step(walker.act(obs, mask))
                done = term or trunc
    return same / total


def _mean(values: list[float]) -> float:
    arr = np.asarray(values, dtype=np.float64)
    return float("nan") if np.isnan(arr).all() else float(np.nanmean(arr))


def run_check(
    train_configs: list[ScenarioConfig],
    eval_configs: list[ScenarioConfig],
    seeds: list[int],
    steps: int,
    episodes: int,
    out_dir: Path,
    config: DDQNConfig = DEFAULT_CONFIG,
    adversary_scale: tuple[float, float] | None = DEFAULT_ADVERSARY_SCALE,
    threshold_params: ThresholdParams | None = None,
) -> dict[str, Any]:
    """``threshold_params`` skips the (slow) rule tuning on the training configs."""
    if any(c.split != "eval" for c in eval_configs):
        raise ValueError("the check must score held-out configs with split=eval")
    out_dir.mkdir(parents=True, exist_ok=True)
    ep_seeds = range(EPISODE_SEED_START, EPISODE_SEED_START + episodes)
    tuned = threshold_params is None
    thr_params = threshold_params or tune_threshold_rules(train_configs)[0]
    # rows[policy][training seed] -> one dict per (config, episode seed), in a fixed order
    rows: dict[str, dict[int, list[dict[str, Any]]]] = {p: {} for p in POLICIES}
    per_seed: dict[str, Any] = {}
    for seed in seeds:
        manifest = train(
            train_configs, seed, steps, out_dir, config, adversary_scale=adversary_scale
        )
        trained, _ = load_checkpoint(out_dir / f"ddqn_seed{seed}.pt")
        untrained = untrained_agent(config, seed)
        policies: dict[str, Policy] = {
            "ddqn_trained": GreedyAgentPolicy(trained, "ddqn_trained"),
            "ddqn_untrained": GreedyAgentPolicy(untrained, "ddqn_untrained"),
            "random": RandomValidPolicy(seed=seed),
            "noop": NoopPolicy(),
            "threshold_rules": ThresholdRulesPolicy(thr_params),
        }
        for name, policy in policies.items():
            rows[name][seed] = [
                {"config": cfg.name, "episode_seed": s, **run_episode(env, policy, s)[0]}
                for cfg in eval_configs
                for env in [DefenseSimEnv(cfg)]
                for s in ep_seeds
            ]
        per_seed[str(seed)] = {
            "checkpoint_sha256": manifest["checkpoint_sha256"],
            "gradient_updates": manifest["gradient_updates"],
            "param_abs_change_from_init": param_distance(trained, untrained),
            "greedy_action_agreement_with_untrained": action_agreement(
                trained, untrained, eval_configs, range(EPISODE_SEED_START, EPISODE_SEED_START + 5)
            ),
        }

    summary_policies: dict[str, Any] = {}
    for name in POLICIES:
        entry: dict[str, Any] = {}
        for metric in REPORTED:
            seed_means = [_mean([r[metric] for r in rows[name][s]]) for s in seeds]
            entry[metric] = {
                "mean": _mean(seed_means),
                "ci95_over_training_seeds": bootstrap_ci(np.asarray(seed_means)),
                "per_seed": seed_means,
            }
        summary_policies[name] = entry

    # Paired on (training seed, config, episode seed): every policy saw the same episodes.
    paired: dict[str, Any] = {}
    for base in POLICIES[1:]:
        diffs = np.asarray(
            [
                t["return"] - b["return"]
                for s in seeds
                for t, b in zip(rows["ddqn_trained"][s], rows[base][s], strict=True)
            ]
        )
        lo, hi = bootstrap_ci(diffs)
        paired[f"ddqn_trained_minus_{base}"] = {
            "mean_return_diff": float(diffs.mean()),
            "ci95_over_episodes": [lo, hi],
            "episodes": int(len(diffs)),
            "trained_better": bool(lo > 0),
            "trained_worse": bool(hi < 0),
        }

    summary = {
        "caveat": CAVEAT,
        "kind": "learning check (not a protocol-17 evaluation)",
        "git_sha": git_sha(),
        "torch": torch.__version__,
        "training_seeds": seeds,
        "training_steps": steps,
        "ddqn_config": config.model_dump(mode="json"),
        "adversary_scale": list(adversary_scale) if adversary_scale else None,
        "train_configs": {c.name: c.config_hash() for c in train_configs},
        "eval_configs": {c.name: c.config_hash() for c in eval_configs},
        "episode_seed_range": [ep_seeds.start, ep_seeds.stop - 1],
        "episodes_per_config_per_seed": episodes,
        "threshold_rules": {
            "params": thr_params.__dict__,
            "tuned_on": "train configs" if tuned else "not tuned (supplied)",
        },
        "per_training_seed": per_seed,
        "policies": summary_policies,
        "paired_return": paired,
    }
    (out_dir / "learning_check.json").write_text(json.dumps(summary, indent=2))
    (out_dir / "learning_check.md").write_text(render(summary))
    return summary


def render(summary: dict[str, Any]) -> str:
    n = len(summary["training_seeds"])
    lines = [
        "# Learning check: trained vs untrained vs baselines",
        "",
        f"_{summary['caveat']}_",
        "",
        f"Commit `{summary['git_sha'][:12]}`, {n} training seeds {summary['training_seeds']}, "
        f"{summary['training_steps']:,} steps each, held-out eval configs, episode seeds "
        f"{summary['episode_seed_range'][0]}-{summary['episode_seed_range'][1]} "
        f"({summary['episodes_per_config_per_seed']} per config per seed). "
        "A short check, not the protocol-17 evaluation.",
        "",
        "| Policy | Return [95% CI over seeds] | Compromise % | False disruption % | Uptime % |",
        "|---|---|---|---|---|",
    ]
    for name, m in summary["policies"].items():
        lo, hi = m["return"]["ci95_over_training_seeds"]
        fd = m["false_disruption_rate"]["mean"]
        lines.append(
            f"| {name} | {m['return']['mean']:.1f} [{lo:.1f}, {hi:.1f}] "
            f"| {100 * m['compromise_rate']['mean']:.1f} "
            f"| {'n/a' if fd != fd else f'{100 * fd:.1f}'} "
            f"| {100 * m['service_uptime']['mean']:.1f} |"
        )
    lines += [
        "",
        "## Paired return difference (same episodes)",
        "",
        "| Comparison | Mean diff [95% CI over episodes] | Episodes | Verdict |",
        "|---|---|---|---|",
    ]
    for name, p in summary["paired_return"].items():
        verdict = (
            "trained better"
            if p["trained_better"]
            else "trained worse"
            if p["trained_worse"]
            else "no clear difference"
        )
        lo, hi = p["ci95_over_episodes"]
        lines.append(
            f"| {name} | {p['mean_return_diff']:+.1f} [{lo:+.1f}, {hi:+.1f}] "
            f"| {p['episodes']} | {verdict} |"
        )
    lines += [
        "",
        "## Did the parameters and the behaviour change?",
        "",
        "| Seed | Gradient updates | Sum of abs weight change from init | Same greedy action as untrained |",
        "|---|---|---|---|",
    ]
    for seed, s in summary["per_training_seed"].items():
        lines.append(
            f"| {seed} | {s['gradient_updates']:,} | {s['param_abs_change_from_init']:.1f} "
            f"| {100 * s['greedy_action_agreement_with_untrained']:.1f}% of states |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--steps", type=int, default=150_000)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--episodes", type=int, default=100, help="per held-out config per seed")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ddqn-config", type=Path, help="YAML of DDQNConfig overrides")
    args = ap.parse_args()
    config = (
        DDQNConfig(**yaml.safe_load(args.ddqn_config.read_text()))
        if args.ddqn_config
        else DEFAULT_CONFIG
    )
    summary = run_check(
        load_configs(default_config_paths("train")),
        load_configs(default_config_paths("eval")),
        args.seeds,
        args.steps,
        args.episodes,
        args.out,
        config,
    )
    print(render(summary))


if __name__ == "__main__":
    main()
