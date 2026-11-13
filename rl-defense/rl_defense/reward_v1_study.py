"""Does charging for standing disruption of healthy nodes give a more useful policy?

    python -m rl_defense.reward_v1_study --out results/reward-v1

Background (results/reward-v1/REPORT.md): under the v0 reward the trained DDQN keeps the two
internet-exposed nodes rate-limited without any alert signal, because v0 prices that at
0.3 x criticality x c_disrupt per step (0.027 for the gateway). DefenseSimEnv-v1 keeps the
dynamics, observation and actions and adds ``c_false_disrupt``: a per-step cost for each
uncompromised node under a disruptive control, not scaled by criticality.

One arm per value of ``c_false_disrupt`` (0 = the v0 reward, i.e. the original policy
retrained with this study's budget). Every arm uses the same training seeds, steps, DDQN
settings and in-training checkpoint selection. Baselines are re-tuned per arm on the
training configs under that arm's reward.

Selection rule, fixed before any run and applied to VALIDATION only (training configs,
episode seeds 2000-2049): an arm qualifies if its false-disruption rate is at most
``FD_LIMIT`` and its benign-disruption load is at most half the c=0 arm's; among qualifying
arms the lowest compromise rate wins. Held-out numbers are reported for every arm, with the
validation-selected arm marked; they are not used to choose.

Security metrics (compromise, db loss, false disruption, benign load, uptime) do not depend
on the reward version, so policies trained under different rewards are comparable on them.
Return is reported under both rewards. Simulation output only.
"""

from __future__ import annotations

import argparse
import json
import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from rl_defense.agents.ddqn import DDQNConfig
from rl_defense.baselines import (
    ExposedGuardPolicy,
    NoopPolicy,
    RandomValidPolicy,
    ThresholdRulesPolicy,
    tune_exposed_guard,
    tune_threshold_rules,
)
from rl_defense.baselines.policies import Policy
from rl_defense.checkpoint import git_sha, load_checkpoint
from rl_defense.envs import DefenseSimEnv, default_config_paths, load_configs
from rl_defense.envs.config import ENV_V1, ScenarioConfig
from rl_defense.envs.defense_sim import DB_INDEX, DISRUPTIVE, N_NODES, decode_action
from rl_defense.evaluate import CAVEAT, bootstrap_ci
from rl_defense.learning_check import GreedyAgentPolicy
from rl_defense.train import train

DDQN = DDQNConfig(lr=3e-4, n_step=3, eps_decay_steps=100_000)
ADVERSARY_SCALE = (0.5, 2.5)
STEPS, SELECT_EVERY, SELECT_START = 300_000, 25_000, 100_000
ARMS: tuple[float, ...] = (0.0, 0.1, 0.25, 0.5)
VALIDATION_SEEDS = range(2000, 2050)
HELD_OUT_SEEDS = range(1000, 1100)
FD_LIMIT = 0.40
METRICS = (
    "return_v0",
    "return_arm",
    "compromise_rate",
    "db_loss_rate",
    "false_disruption_rate",
    "benign_load",
    "disruptive_actions",
    "service_uptime",
    "invalid_actions",
)


def to_arm(cfg: ScenarioConfig, c: float) -> ScenarioConfig:
    """The same scenario under the arm's reward. c = 0 returns the v0 config unchanged."""
    if c == 0.0:
        return cfg
    return cfg.model_copy(
        update={
            "env_version": ENV_V1,
            "reward": cfg.reward.model_copy(update={"c_false_disrupt": c}),
        }
    )


def episode_metrics(cfg: ScenarioConfig, policy: Policy, seed: int) -> dict[str, float]:
    """One episode. ``cfg`` fixes the reward the policy is scored under (``return_arm``);
    ``return_v0`` removes the v1 term so every policy also has a return on a common scale."""
    env = DefenseSimEnv(cfg)
    obs, info = env.reset(seed=seed)
    policy.reset(seed)
    crit = np.array([n.criticality for n in cfg.nodes])
    total = load = unavailable = 0.0
    disruptive = benign = invalid = steps = 0
    done = False
    while not done:
        action = policy.act(obs, info["action_mask"])
        name, _ = decode_action(action)
        obs, reward, term, trunc, info = env.step(action)
        ev = info["events"]
        total += reward
        load += ev["benign_disruption_load"]
        invalid += int(ev["invalid_action"])
        if name in DISRUPTIVE and not ev["invalid_action"]:
            disruptive += 1
            benign += int(ev["disruptive_on_benign"])
        isolated = np.array([env._obs_state.isolate_timer[i] > 0 for i in range(N_NODES)])
        unavailable += float(np.dot(isolated, crit) / crit.sum())
        steps += 1
        done = term or trunc
    m = info["metrics"]
    return {
        "return_arm": total,
        "return_v0": total + cfg.reward.c_false_disrupt * load,
        "compromise_rate": float(m["ever_impact"]),
        "db_loss_rate": float(m["stages"][DB_INDEX] == 3),
        "false_disruption_rate": benign / disruptive if disruptive else math.nan,
        # mean number of healthy nodes under a control per step (isolation 1.0, rate-limit 0.3)
        "benign_load": load / steps,
        "disruptive_actions": float(disruptive),
        "service_uptime": 1.0 - unavailable / steps,
        "invalid_actions": float(invalid),
    }


def score(policy: Policy, configs: list[ScenarioConfig], seeds: range) -> dict[str, float]:
    rows = [episode_metrics(cfg, policy, s) for cfg in configs for s in seeds]
    out = {}
    for k in METRICS:
        vals = np.array([r[k] for r in rows], dtype=np.float64)
        out[k] = float("nan") if np.isnan(vals).all() else float(np.nanmean(vals))
    return out


def _train_one(job: tuple[float, int, int, str]) -> dict[str, Any]:
    c, seed, steps, out = job
    configs = [to_arm(cfg, c) for cfg in load_configs(default_config_paths("train"))]
    scale = steps / STEPS  # tests shrink the run; the schedule shrinks with it
    manifest = train(
        configs,
        seed,
        steps,
        Path(out) / arm_dir(c),
        DDQN.model_copy(update={"eps_decay_steps": max(1, int(DDQN.eps_decay_steps * scale))}),
        adversary_scale=ADVERSARY_SCALE,
        select_every=max(1, int(SELECT_EVERY * scale)),
        select_start=int(SELECT_START * scale),
    )
    return {"c": c, "seed": seed, "checkpoint_sha256": manifest["checkpoint_sha256"]}


def arm_dir(c: float) -> str:
    return f"c{c:g}".replace(".", "p")


def _score_arm(job: tuple[float, list[int], str, bool]) -> dict[str, Any]:
    """Validation and held-out rows for one arm: its DDQN seeds and its re-tuned baselines."""
    c, seeds, out, tune = job
    train_cfgs = [to_arm(cfg, c) for cfg in load_configs(default_config_paths("train"))]
    eval_cfgs = [to_arm(cfg, c) for cfg in load_configs(default_config_paths("eval"))]
    thr_params, _ = tune_threshold_rules(train_cfgs) if tune else (None, None)
    guard_thr, guard_grid = tune_exposed_guard(train_cfgs)
    result: dict[str, Any] = {
        "c_false_disrupt": c,
        "tuned": {
            "threshold_rules": thr_params.__dict__ if thr_params else None,
            "exposed_guard_isolate_anomaly": guard_thr,
            "exposed_guard_grid": guard_grid,
        },
        "validation": {},
        "held_out": {},
    }
    for split, cfgs, ep_seeds in (
        ("validation", train_cfgs, VALIDATION_SEEDS),
        ("held_out", eval_cfgs, HELD_OUT_SEEDS),
    ):
        per_seed = []
        for seed in seeds:
            agent, _ = load_checkpoint(Path(out) / arm_dir(c) / f"ddqn_seed{seed}.pt")
            per_seed.append(score(GreedyAgentPolicy(agent, "ddqn"), cfgs, ep_seeds))
        result[split]["ddqn"] = _over_seeds(per_seed)
        baselines: dict[str, Policy] = {
            "exposed_guard": ExposedGuardPolicy(guard_thr),
            "noop": NoopPolicy(),
        }
        if thr_params:
            baselines["threshold_rules"] = ThresholdRulesPolicy(thr_params)
        for name, policy in baselines.items():
            result[split][name] = _over_seeds([score(policy, cfgs, ep_seeds)])
        result[split]["random"] = _over_seeds(
            [score(RandomValidPolicy(seed=s), cfgs, ep_seeds) for s in seeds]
        )
    return result


def _over_seeds(per_seed: list[dict[str, float]]) -> dict[str, Any]:
    out = {}
    for k in METRICS:
        vals = np.array([r[k] for r in per_seed], dtype=np.float64)
        lo, hi = bootstrap_ci(vals)
        out[k] = {
            "mean": float("nan") if np.isnan(vals).all() else float(np.nanmean(vals)),
            "ci95": [lo, hi],
            "per_seed": vals.tolist(),
        }
    return out


def select_arm(arms: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the pre-stated rule to validation numbers only."""
    ref = next(a for a in arms if a["c_false_disrupt"] == 0.0)["validation"]["ddqn"]
    limit = 0.5 * ref["benign_load"]["mean"]
    table = []
    for a in arms:
        v = a["validation"]["ddqn"]
        ok = (
            a["c_false_disrupt"] > 0.0
            and v["false_disruption_rate"]["mean"] <= FD_LIMIT
            and v["benign_load"]["mean"] <= limit
        )
        table.append(
            {
                "c_false_disrupt": a["c_false_disrupt"],
                "false_disruption_rate": v["false_disruption_rate"]["mean"],
                "benign_load": v["benign_load"]["mean"],
                "compromise_rate": v["compromise_rate"]["mean"],
                "qualifies": bool(ok),
            }
        )
    winners = [t for t in table if t["qualifies"]]
    best = min(winners, key=lambda t: t["compromise_rate"]) if winners else None
    return {
        "rule": f"false disruption <= {FD_LIMIT:.0%} and benign load <= {limit:.4f} "
        "(half the c=0 arm); lowest compromise rate among those",
        "validation": table,
        "selected_c_false_disrupt": best["c_false_disrupt"] if best else None,
    }


def run_study(
    out: Path,
    arms: tuple[float, ...] = ARMS,
    seeds: tuple[int, ...] = (0, 1, 2, 3, 4),
    steps: int = STEPS,
    workers: int = 8,
    tune_rules: bool = True,
) -> dict[str, Any]:
    if 0.0 not in arms:
        raise ValueError("the study needs the c=0 arm: it is the reference policy")
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(c, s, steps, str(out)) for c in arms for s in seeds]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        trained = list(pool.map(_train_one, jobs))
        scored = list(pool.map(_score_arm, [(c, list(seeds), str(out), tune_rules) for c in arms]))
    summary = {
        "caveat": CAVEAT,
        "kind": "reward-v1 study (DefenseSimEnv-v1 reward vs the v0 reward, same budget)",
        "git_sha": git_sha(),
        "training_seeds": list(seeds),
        "training_steps": steps,
        "ddqn_config": DDQN.model_dump(mode="json"),
        "adversary_scale": list(ADVERSARY_SCALE),
        "selection_in_training": [SELECT_EVERY, SELECT_START],
        "validation_episode_seeds": [VALIDATION_SEEDS.start, VALIDATION_SEEDS.stop - 1],
        "held_out_episode_seeds": [HELD_OUT_SEEDS.start, HELD_OUT_SEEDS.stop - 1],
        "checkpoints": trained,
        "arms": scored,
        "selection": select_arm(scored),
    }
    (out / "study.json").write_text(json.dumps(summary, indent=2))
    (out / "study.md").write_text(render(summary))
    return summary


def _row(name: str, m: dict[str, Any]) -> str:
    def pct(k: str) -> str:
        v = m[k]["mean"]
        return "n/a" if v != v else f"{100 * v:.1f}"

    lo, hi = m["compromise_rate"]["ci95"]
    return (
        f"| {name} | {m['return_v0']['mean']:.1f} | {m['return_arm']['mean']:.1f} "
        f"| {pct('compromise_rate')} [{100 * lo:.1f}, {100 * hi:.1f}] | {pct('db_loss_rate')} "
        f"| {pct('false_disruption_rate')} | {m['benign_load']['mean']:.3f} "
        f"| {m['disruptive_actions']['mean']:.1f} | {pct('service_uptime')} "
        f"| {m['invalid_actions']['mean']:.0f} |"
    )


def render(summary: dict[str, Any]) -> str:
    sel = summary["selection"]
    lines = [
        "# Reward-v1 study",
        "",
        f"_{summary['caveat']}_",
        "",
        f"Commit `{summary['git_sha'][:12]}`. Training seeds {summary['training_seeds']}, "
        f"{summary['training_steps']:,} steps each, in-training checkpoint selection. "
        "CIs are 95% bootstrap over training seeds. Benign load is the mean number of healthy "
        "nodes under a control per step (isolation 1.0, rate-limit 0.3).",
        "",
        f"Selection rule (validation only): {sel['rule']}.",
        f"Selected `c_false_disrupt`: **{sel['selected_c_false_disrupt']}**.",
        "",
    ]
    header = (
        "| Policy | Return (v0 reward) | Return (arm reward) | Compromise % [CI] | db lost % "
        "| False disruption % | Benign load | Disruptive actions/ep | Uptime % | Invalid |"
    )
    for split, title in (("validation", "Validation"), ("held_out", "Held-out")):
        lines += [f"## {title}", ""]
        for arm in summary["arms"]:
            c = arm["c_false_disrupt"]
            mark = " (selected)" if c == sel["selected_c_false_disrupt"] else ""
            lines += [
                f"### c_false_disrupt = {c:g}{mark}",
                "",
                header,
                "|---|---|---|---|---|---|---|---|---|---|",
            ]
            lines += [_row(name, m) for name, m in arm[split].items()]
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--arms", type=float, nargs="+", default=list(ARMS))
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    summary = run_study(args.out, tuple(args.arms), tuple(args.seeds), args.steps, args.workers)
    print(render(summary))


if __name__ == "__main__":
    main()
