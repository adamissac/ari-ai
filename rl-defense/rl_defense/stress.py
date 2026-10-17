"""Generalization stress test: scale adversary aggressiveness on held-out scenarios.

    python -m rl_defense.stress --run-dir runs/<run_id> [--episodes 50]

Stress configs are derived from the held-out eval configs by multiplying every
adversary transition probability by a factor. They are evaluation-only (never
used for training or tuning) and are hashed in the output like any other config.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from rl_defense.baselines import (
    NoopPolicy,
    RandomValidPolicy,
    ThresholdParams,
    ThresholdRulesPolicy,
)
from rl_defense.envs import DefenseSimEnv, default_config_paths, load_configs
from rl_defense.envs.config import ScenarioConfig
from rl_defense.evaluate import CAVEAT, DDQNPolicy, bootstrap_ci, run_episode

FACTORS = (0.5, 1.0, 1.5, 2.0, 2.5)
STRESS_SEEDS = range(3000, 3050)  # disjoint from eval (1000-1099) and validation (2000-2099)


def scaled(cfg: ScenarioConfig, factor: float) -> ScenarioConfig:
    adv = cfg.adversary.model_copy(
        update={
            k: min(1.0, getattr(cfg.adversary, k) * factor)
            for k in ("entry_prob", "lateral_prob", "escalate_prob", "impact_prob")
        }
    )
    return cfg.model_copy(update={"name": f"{cfg.name}_x{factor:g}", "adversary": adv})


def stress(
    run_dir: Path, episodes: range = STRESS_SEEDS, factors: tuple[float, ...] = FACTORS
) -> dict[str, Any]:
    summary = json.loads((run_dir / "eval_summary.json").read_text())
    base_configs = load_configs(default_config_paths("eval"))
    seeds = summary["training_seeds"]
    thr = ThresholdParams(**summary["threshold_rules"]["params"])
    policies = {
        "ddqn": lambda s: DDQNPolicy(run_dir / f"ddqn_seed{s}.pt"),
        "threshold_rules": lambda s: ThresholdRulesPolicy(thr),
        "random": lambda s: RandomValidPolicy(seed=s),
        "noop": lambda s: NoopPolicy(),
    }
    results: dict[str, Any] = {}
    for factor in factors:
        cfgs = [scaled(c, factor) for c in base_configs]
        results[f"{factor:g}"] = {
            "config_hashes": {c.name: c.config_hash() for c in cfgs},
            "policies": {},
        }
        for pname, make in policies.items():
            per_seed = {
                "return": [],
                "compromise_rate": [],
                "db_loss_rate": [],
                "service_uptime": [],
            }
            for s in seeds:
                policy = make(s)
                rows = [run_episode(DefenseSimEnv(c), policy, e)[0] for c in cfgs for e in episodes]
                per_seed["return"].append(float(np.mean([r["return"] for r in rows])))
                per_seed["compromise_rate"].append(
                    float(np.mean([r["compromise_rate"] for r in rows]))
                )
                per_seed["db_loss_rate"].append(
                    float(np.mean(["db" in r["impact_nodes"] for r in rows]))
                )
                per_seed["service_uptime"].append(
                    float(np.mean([r["service_uptime"] for r in rows]))
                )
            results[f"{factor:g}"]["policies"][pname] = {
                k: {"mean": float(np.mean(v)), "ci95": bootstrap_ci(np.array(v)), "per_seed": v}
                for k, v in per_seed.items()
            }
    out = {
        "caveat": CAVEAT,
        "source_run": run_dir.name,
        "git_sha": summary["git_sha"],
        "training_seeds": seeds,
        "episodes_per_config_per_seed": len(episodes),
        "episode_seed_range": [episodes.start, episodes.stop - 1],
        "factors": list(factors),
        "results": results,
    }
    (run_dir / "stress_summary.json").write_text(json.dumps(out, indent=2))
    (run_dir / "stress_table.md").write_text(render(out))
    return out


def _f(m: dict[str, Any], pct: bool = False) -> str:
    s = 100.0 if pct else 1.0
    lo, hi = m["ci95"]
    if m["mean"] is None or math.isnan(m["mean"]):
        return "n/a"
    return f"{m['mean'] * s:.1f} [{lo * s:.1f}, {hi * s:.1f}]"


def render(out: dict[str, Any]) -> str:
    lines = [
        "# Stress test: adversary aggressiveness",
        "",
        f"Held-out eval configs with every adversary transition probability × factor. "
        f"{len(out['training_seeds'])} training seeds × {out['episodes_per_config_per_seed']} episodes "
        f"× 3 configs per cell (episode seeds {out['episode_seed_range'][0]}–{out['episode_seed_range'][1]}). "
        "Mean [95% bootstrap CI across training seeds]. Factor 1.0 = the held-out configs.",
        "",
    ]
    for metric, title, pct in (
        ("return", "Return", False),
        ("compromise_rate", "Compromise %", True),
        ("db_loss_rate", "db lost %", True),
        ("service_uptime", "Uptime %", True),
    ):
        pols = list(next(iter(out["results"].values()))["policies"])
        lines += [
            f"## {title}",
            "",
            "| Factor | " + " | ".join(pols) + " |",
            "|---|" + "---|" * len(pols),
        ]
        for factor, cell in out["results"].items():
            lines.append(
                f"| ×{factor} | "
                + " | ".join(_f(cell["policies"][p][metric], pct) for p in pols)
                + " |"
            )
        lines.append("")
    lines.append(f"*{out['caveat']}*")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--episodes", type=int, default=len(STRESS_SEEDS))
    args = ap.parse_args()
    out = stress(
        args.run_dir, episodes=range(STRESS_SEEDS.start, STRESS_SEEDS.start + args.episodes)
    )
    print(render(out))


if __name__ == "__main__":
    main()
