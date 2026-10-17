"""Evaluate DDQN checkpoints and baselines per docs/17_RL_EVALUATION_PROTOCOL.md.

    python -m rl_defense.evaluate --run-dir runs/<run_id>

Loads ``ddqn_seed*.pt`` from the run dir, evaluates every policy on the HELD-OUT
eval configs with eval seeds 1000-1099, and writes ``eval_summary.json``,
``eval_table.md``, raw per-episode metrics and a few full trajectories.
"""

from __future__ import annotations

import argparse
import json
import math
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

from rl_defense import ENV_ID
from rl_defense.baselines import (
    NoopPolicy,
    RandomValidPolicy,
    ThresholdRulesPolicy,
    tune_threshold_rules,
)
from rl_defense.baselines.policies import Policy
from rl_defense.checkpoint import git_sha, load_checkpoint
from rl_defense.envs import DefenseSimEnv, default_config_paths, load_configs
from rl_defense.envs.config import ScenarioConfig
from rl_defense.envs.defense_sim import (
    DISRUPTIVE,
    ESCALATE_ACTION,
    NODE_FEATURES,
    NOOP_ACTION,
    REWARD_COMPONENTS,
    decode_action,
)

EVAL_SEEDS = range(1000, 1100)


def _nanmean(values: Any, axis: int | None = None) -> Any:
    """Mean ignoring NaN; NaN (without a warning) when every value is NaN, e.g. no disruptive actions."""
    arr = np.asarray(values, dtype=np.float64)
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(arr, axis=axis)


METRICS = (
    "return",
    "compromise_rate",
    "time_to_containment",
    "false_disruption_rate",
    "escalations",
    "action_cost",
    "service_uptime",
    "invalid_actions",
)
HIGHER_IS_BETTER = {"return": True, "service_uptime": True}
_ISOLATED = NODE_FEATURES.index("isolated")
CAVEAT = "Results are from a simulated environment and do not establish real-world effectiveness."


class DDQNPolicy:
    name = "ddqn"

    def __init__(self, checkpoint: Path) -> None:
        self.agent, self.manifest = load_checkpoint(checkpoint)

    def reset(self, seed: int) -> None:
        pass

    def act(self, obs: np.ndarray, mask: np.ndarray) -> int:
        return self.agent.act(obs, mask, epsilon=0.0)


def run_episode(
    env: DefenseSimEnv, policy: Policy, seed: int, record: bool = False
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    cfg = env.config
    obs, info = env.reset(seed=seed)
    policy.reset(seed)
    total, done = 0.0, False
    disruptive = benign_disruptive = escalations = invalid = non_noop = 0
    unavailable = 0.0
    crit = np.array([n.criticality for n in cfg.nodes])
    trajectory: list[dict[str, Any]] = []
    component_totals = dict.fromkeys(REWARD_COMPONENTS, 0.0)
    while not done:
        mask = info["action_mask"]
        action = policy.act(obs, mask)
        name, _ = decode_action(action)
        next_obs, reward, term, trunc, next_info = env.step(action)
        ev = next_info["events"]
        for key, value in ev["reward_components"].items():
            component_totals[key] += value
        invalid += int(ev["invalid_action"])
        non_noop += int(action != NOOP_ACTION and not ev["invalid_action"])
        escalations += int(action == ESCALATE_ACTION and not ev["invalid_action"])
        if name in DISRUPTIVE and not ev["invalid_action"]:
            disruptive += 1
            benign_disruptive += int(ev["disruptive_on_benign"])
        isolated = next_obs[[i * len(NODE_FEATURES) + _ISOLATED for i in range(len(crit))]]
        unavailable += float(np.dot(isolated, crit) / crit.sum())
        if record:
            trajectory.append(
                {
                    "t": info["t"],
                    "action": next_info["action"],
                    "reward": round(reward, 4),
                    "reward_components": {
                        k: round(v, 4) for k, v in ev["reward_components"].items()
                    },
                    "observation": [round(float(x), 4) for x in obs],
                    "hidden_stages_for_replay_only": next_info["metrics"]["stages"],
                }
            )
        total += reward
        obs, info, done = next_obs, next_info, term or trunc
    m = info["metrics"]
    steps = info["t"]
    if m["first_foothold_t"] is None:
        ttc = math.nan  # adversary never got in: TTC undefined, excluded from mean
    elif m["containment_t"] is not None:
        ttc = m["containment_t"] - m["first_foothold_t"]
    else:
        ttc = cfg.horizon - m["first_foothold_t"]  # censored at horizon
    r = cfg.reward
    return {
        "return": total,
        "compromise_rate": float(m["ever_impact"]),
        "time_to_containment": float(ttc),
        "false_disruption_rate": benign_disruptive / disruptive if disruptive else math.nan,
        "escalations": float(escalations),
        "action_cost": non_noop * r.c_action + escalations * r.c_escalate,
        "service_uptime": 1.0 - unavailable / max(1, steps),
        "invalid_actions": float(invalid),
        "length": float(steps),
        "reward_components": component_totals,
    }, trajectory


def bootstrap_ci(values: np.ndarray, n: int = 10_000, seed: int = 0) -> tuple[float, float]:
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return (math.nan, math.nan)
    if len(values) == 1 or np.allclose(values, values[0]):
        return (float(values[0]), float(values[0]))
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(n, len(values)), replace=True).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def holm(pvalues: dict[str, float], alpha: float = 0.05) -> dict[str, bool]:
    ordered = sorted((p, k) for k, p in pvalues.items() if not math.isnan(p))
    m, result, still = len(ordered), {k: False for k in pvalues}, True
    for i, (p, k) in enumerate(ordered):
        still = still and p <= alpha / (m - i)
        result[k] = still
    return result


def compare(a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    """Welch's t-test across training seeds; effect size as mean difference and Cohen's d."""
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) == 0 or len(b) == 0:
        return {"mean_diff": math.nan, "cohens_d": math.nan, "p_value": math.nan}
    diff = float(a.mean() - b.mean())
    pooled = math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2) if len(a) > 1 and len(b) > 1 else 0.0
    if pooled == 0.0:
        p = 0.0 if diff != 0 else 1.0
        d = math.inf if diff > 0 else (-math.inf if diff < 0 else 0.0)
    else:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "ignore", RuntimeWarning
            )  # near-identical seeds (deterministic baselines)
            p = float(stats.ttest_ind(a, b, equal_var=False).pvalue)
        d = diff / pooled
    return {"mean_diff": diff, "cohens_d": d, "p_value": p}


def evaluate(
    run_dir: Path,
    eval_configs: list[ScenarioConfig],
    train_configs: list[ScenarioConfig],
    episodes: range = EVAL_SEEDS,
    trajectories_per_policy: int = 3,
) -> dict[str, Any]:
    if any(c.split != "eval" for c in eval_configs):
        raise ValueError("evaluation must use held-out configs with split=eval")
    checkpoints = sorted(run_dir.glob("ddqn_seed*.pt"))
    if not checkpoints:
        raise FileNotFoundError(f"no ddqn_seed*.pt checkpoints in {run_dir}")
    training_seeds = [int(p.stem.removeprefix("ddqn_seed")) for p in checkpoints]
    thr_params, thr_grid = tune_threshold_rules(train_configs)

    factories: dict[str, Callable[[int, Path], Policy]] = {
        "ddqn": lambda _s, ckpt: DDQNPolicy(ckpt),
        "random": lambda s, _c: RandomValidPolicy(seed=s),
        "noop": lambda _s, _c: NoopPolicy(),
        "threshold_rules": lambda _s, _c: ThresholdRulesPolicy(thr_params),
    }
    raw_path = run_dir / "eval_episodes.jsonl"
    traj_dir = run_dir / "trajectories"
    traj_dir.mkdir(exist_ok=True)
    # per_seed[policy][config][metric] -> list over training seeds of per-seed means
    per_seed: dict[str, dict[str, dict[str, list[float]]]] = {}
    with raw_path.open("w") as raw:
        for pname, make in factories.items():
            per_seed[pname] = {c.name: {k: [] for k in METRICS} for c in eval_configs}
            for tseed, ckpt in zip(training_seeds, checkpoints, strict=True):
                policy = make(tseed, ckpt)
                for cfg in eval_configs:
                    env = DefenseSimEnv(cfg)
                    rows = []
                    for i, ep_seed in enumerate(episodes):
                        record = tseed == training_seeds[0] and i < trajectories_per_policy
                        row, traj = run_episode(env, policy, ep_seed, record)
                        rows.append(row)
                        raw.write(
                            json.dumps(
                                {
                                    "policy": pname,
                                    "training_seed": tseed,
                                    "config": cfg.name,
                                    "episode_seed": ep_seed,
                                    **row,
                                }
                            )
                            + "\n"
                        )
                        if record:
                            (traj_dir / f"{pname}_{cfg.name}_ep{ep_seed}.json").write_text(
                                json.dumps(
                                    {
                                        "policy": pname,
                                        "config": cfg.name,
                                        "episode_seed": ep_seed,
                                        "training_seed": tseed,
                                        "steps": traj,
                                    }
                                )
                            )
                    for k in METRICS:
                        per_seed[pname][cfg.name][k].append(float(_nanmean([r[k] for r in rows])))

    summary_policies: dict[str, Any] = {}
    for pname, by_cfg in per_seed.items():
        entry: dict[str, Any] = {"per_config": {}, "pooled": {}}
        pooled_vals = {k: _nanmean([by_cfg[c][k] for c in by_cfg], axis=0) for k in METRICS}
        for cname, metrics in by_cfg.items():
            entry["per_config"][cname] = {
                k: {"mean": float(_nanmean(v)), "ci95": bootstrap_ci(np.array(v)), "per_seed": v}
                for k, v in metrics.items()
            }
        entry["pooled"] = {
            k: {"mean": float(_nanmean(v)), "ci95": bootstrap_ci(v), "per_seed": v.tolist()}
            for k, v in pooled_vals.items()
        }
        summary_policies[pname] = entry

    comparisons: dict[str, Any] = {}
    for base in ("random", "noop", "threshold_rules"):
        tests = {
            k: compare(
                np.array(summary_policies["ddqn"]["pooled"][k]["per_seed"]),
                np.array(summary_policies[base]["pooled"][k]["per_seed"]),
            )
            for k in METRICS
            if k != "invalid_actions"
        }
        significant = holm({k: t["p_value"] for k, t in tests.items()})
        for k, t in tests.items():
            if math.isnan(t["mean_diff"]):
                t.update(
                    holm_significant=False,
                    ddqn_better=False,
                    verdict="undefined (metric n/a for one policy)",
                )
                continue
            better = t["mean_diff"] > 0 if HIGHER_IS_BETTER.get(k, False) else t["mean_diff"] < 0
            t["holm_significant"] = significant[k]
            t["ddqn_better"] = bool(better)
            t["verdict"] = (
                ("ddqn better" if better else "ddqn worse")
                if significant[k]
                else "no significant difference"
            )
        comparisons[f"ddqn_vs_{base}"] = tests

    first_manifest = json.loads(checkpoints[0].with_suffix(".manifest.json").read_text())
    summary = {
        "env_id": ENV_ID,
        "caveat": CAVEAT,
        "git_sha": git_sha(),
        "eval_configs": {c.name: c.config_hash() for c in eval_configs},
        "train_configs": {c.name: c.config_hash() for c in train_configs},
        "training_seeds": training_seeds,
        "episodes_per_config_per_seed": len(episodes),
        "eval_seed_range": [episodes.start, episodes.stop - 1],
        "training_steps": first_manifest["steps"],
        "ddqn_config": first_manifest["ddqn_config"],
        "checkpoints": {
            json.loads(p.with_suffix(".manifest.json").read_text())["checkpoint_file"]: json.loads(
                p.with_suffix(".manifest.json").read_text()
            )["checkpoint_sha256"]
            for p in checkpoints
        },
        "threshold_rules": {
            "params": thr_params.__dict__,
            "tuned_on": "train configs, seeds 500-539",
            "grid_size": len(thr_grid),
        },
        "statistics": "Mean and bootstrap 95% CI (10k resamples) across training seeds; each seed value "
        "is the mean over episodes per config. Welch t-test, Holm-corrected across metrics.",
        "policies": summary_policies,
        "comparisons": comparisons,
        "raw_episodes_file": raw_path.name,
        "trajectories_dir": traj_dir.name,
    }
    (run_dir / "eval_summary.json").write_text(json.dumps(summary, indent=2, default=_json_default))
    (run_dir / "eval_table.md").write_text(render_table(summary))
    return summary


def _json_default(o: Any) -> Any:
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    raise TypeError(type(o))


def _fmt(m: dict[str, Any], pct: bool = False) -> str:
    mean, (lo, hi) = m["mean"], m["ci95"]
    if mean is None or math.isnan(mean):
        return "n/a"
    s = 100.0 if pct else 1.0
    return f"{mean * s:.1f} [{lo * s:.1f}, {hi * s:.1f}]"


def _num(x: float, spec: str) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else format(x, spec)


def render_table(summary: dict[str, Any]) -> str:
    lines = [
        f"Env: {summary['env_id']}, eval configs: {', '.join(f'{k} ({v})' for k, v in summary['eval_configs'].items())}",
        f"Training seeds: {summary['training_seeds']} × {summary['episodes_per_config_per_seed']} episodes "
        f"per config (eval seeds {summary['eval_seed_range'][0]}–{summary['eval_seed_range'][1]}); "
        f"{summary['training_steps']} training steps per seed; git {summary['git_sha'][:12]}",
        "",
        "Pooled over held-out configs. Mean [95% bootstrap CI across training seeds].",
        "",
        "| Policy | Return | Compromise % | TTC (steps) | False disruption % | Escalations | Uptime % | Invalid actions |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for pname, entry in summary["policies"].items():
        p = entry["pooled"]
        lines.append(
            f"| {pname} | {_fmt(p['return'])} | {_fmt(p['compromise_rate'], True)} | "
            f"{_fmt(p['time_to_containment'])} | {_fmt(p['false_disruption_rate'], True)} | "
            f"{_fmt(p['escalations'])} | {_fmt(p['service_uptime'], True)} | {_fmt(p['invalid_actions'])} |"
        )
    lines += [
        "",
        "Per held-out config (return / compromise %):",
        "",
        "| Policy | " + " | ".join(summary["eval_configs"]) + " |",
        "|---|" + "---|" * len(summary["eval_configs"]),
    ]
    for pname, entry in summary["policies"].items():
        cells = [
            f"{_fmt(entry['per_config'][c]['return'])} / {_fmt(entry['per_config'][c]['compromise_rate'], True)}"
            for c in summary["eval_configs"]
        ]
        lines.append(f"| {pname} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "DDQN vs baselines (Welch t-test over training seeds, Holm-corrected):",
        "",
        "| Comparison | Metric | Mean diff (ddqn − baseline) | Cohen's d | p | Verdict |",
        "|---|---|---|---|---|---|",
    ]
    for comp, tests in summary["comparisons"].items():
        for k, t in tests.items():
            lines.append(
                f"| {comp} | {k} | {_num(t['mean_diff'], '.3f')} | {_num(t['cohens_d'], '.2f')} | "
                f"{_num(t['p_value'], '.3g')} | {t['verdict']} |"
            )
    lines += ["", f"*{summary['caveat']}*", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--episodes", type=int, default=len(EVAL_SEEDS))
    args = ap.parse_args()
    summary = evaluate(
        args.run_dir,
        load_configs(default_config_paths("eval")),
        load_configs(default_config_paths("train")),
        episodes=range(EVAL_SEEDS.start, EVAL_SEEDS.start + args.episodes),
    )
    print(render_table(summary))


if __name__ == "__main__":
    main()
