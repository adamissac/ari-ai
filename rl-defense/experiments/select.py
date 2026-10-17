"""Validation-only candidate selection (never touches held-out eval configs or seeds).

    python -m experiments.select --round r1 configs/ddqn/*.yaml

Each candidate YAML holds DDQNConfig overrides plus ``steps``. Every candidate is trained
on validation training seeds 10-12 using TRAINING configs, then scored on the same
training configs with validation episode seeds 2000-2099. Held-out ``configs/eval`` and
eval seeds 1000-1099 are reserved for the single final evaluation (docs/17).
"""

from __future__ import annotations

import argparse
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import yaml

VAL_TRAIN_SEEDS = (10, 11, 12)
VAL_EPISODE_SEEDS = range(2000, 2100)
FORBIDDEN_EPISODE_SEEDS = range(1000, 1100)
FORBIDDEN_TRAIN_SEEDS = (0, 1, 2, 3, 4)
NODE_NAMES = ("gateway", "api", "auth", "payments", "db")
METRICS = (
    "return",
    "compromise_rate",
    "db_loss_rate",
    "false_disruption_rate",
    "service_uptime",
    "escalations",
    *(f"impact_{n}" for n in NODE_NAMES),
)
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def load_candidate(path: Path) -> tuple[str, int, dict[str, Any]]:
    data = yaml.safe_load(path.read_text()) or {}
    steps = int(data.pop("steps", 200_000))
    return path.stem, steps, data


def _nanmean(xs: list[float]) -> float:
    vals = [x for x in xs if not math.isnan(x)]
    return float(np.mean(vals)) if vals else math.nan


def validate_episode(env: Any, policy: Any, seed: int, run_episode: Any) -> dict[str, float]:
    """Standard protocol metrics plus db loss and per-node impact.

    Impact is absorbing in DefenseSimEnv (isolation/escalation only reset stages below
    impact), so the final hidden stage tells whether a node was ever impacted. Episodes
    terminate only when the db reaches impact, so length < horizon means the db was lost.
    """
    row, _ = run_episode(env, policy, seed)
    stages = env._hidden.stage  # ground truth, read only for evaluation metrics
    row["db_loss_rate"] = float(row["length"] < env.config.horizon)
    for i, n in enumerate(NODE_NAMES):
        row[f"impact_{n}"] = float(stages[i] == 3)
    return row


def run_job(
    name: str, steps: int, overrides: dict[str, Any], seed: int, run_root: str
) -> dict[str, Any]:
    # Imports inside the worker so each process sets its own torch determinism.
    from rl_defense.agents.ddqn import DDQNConfig
    from rl_defense.envs import DefenseSimEnv, default_config_paths, load_configs
    from rl_defense.evaluate import DDQNPolicy, run_episode
    from rl_defense.train import train

    assert seed not in FORBIDDEN_TRAIN_SEEDS, "seeds 0-4 are reserved for the final run"
    assert not set(VAL_EPISODE_SEEDS) & set(FORBIDDEN_EPISODE_SEEDS)
    configs = load_configs(default_config_paths("train"))
    assert all(c.split == "train" for c in configs)
    run_dir = Path(run_root) / name
    manifest = train(configs, seed, steps, run_dir, DDQNConfig(**overrides), log_every=20_000)
    policy = DDQNPolicy(run_dir / f"ddqn_seed{seed}.pt")
    per_cfg: dict[str, dict[str, float]] = {}
    for cfg in configs:
        env = DefenseSimEnv(cfg)
        rows = [validate_episode(env, policy, s, run_episode) for s in VAL_EPISODE_SEEDS]
        per_cfg[cfg.name] = {k: _nanmean([r[k] for r in rows]) for k in METRICS}
    pooled = {k: _nanmean([per_cfg[c][k] for c in per_cfg]) for k in METRICS}
    return {
        "candidate": name,
        "seed": seed,
        "steps": steps,
        "overrides": overrides,
        "pooled": pooled,
        "per_config": per_cfg,
        "wall_clock_s": manifest["wall_clock_s"],
    }


def summarize(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by: dict[str, list[dict[str, Any]]] = {}
    for j in jobs:
        by.setdefault(j["candidate"], []).append(j)
    rows = []
    for name, js in by.items():
        row: dict[str, Any] = {
            "candidate": name,
            "steps": js[0]["steps"],
            "overrides": js[0]["overrides"],
            "seeds": sorted(j["seed"] for j in js),
        }
        for k in METRICS:
            vals = [j["pooled"][k] for j in js]
            row[k] = _nanmean(vals)
            row[k + "_std"] = float(np.nanstd(vals, ddof=1)) if len(vals) > 1 else 0.0
            row[k + "_per_seed"] = vals
        rows.append(row)
    for r in rows:
        r["worst_seed_return"] = float(min(r["return_per_seed"]))
    return sorted(rows, key=lambda r: -r["return"])


def render(rows: list[dict[str, Any]], round_name: str) -> str:
    out = [
        f"# Validation round {round_name}",
        "",
        f"Training configs only; validation training seeds {list(VAL_TRAIN_SEEDS)}; validation "
        f"episode seeds {VAL_EPISODE_SEEDS.start}–{VAL_EPISODE_SEEDS.stop - 1} (100 per config). "
        "Mean ± std across seeds. Held-out eval configs NOT used. Overrides: "
        "`configs/ddqn/<candidate>.yaml`.",
        "",
        "| Rank | Candidate | Steps | Return | Worst-seed return | Compromise % | db loss % | "
        "False disruption % | Uptime % | Impact % gw/api/auth/pay/db |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        impacts = "/".join(f"{100 * r['impact_' + n]:.0f}" for n in NODE_NAMES)
        out.append(
            f"| {i} | {r['candidate']} | {r['steps']:,} | {r['return']:.1f} ± {r['return_std']:.1f} | "
            f"{r['worst_seed_return']:.1f} | "
            f"{100 * r['compromise_rate']:.1f} ± {100 * r['compromise_rate_std']:.1f} | "
            f"{100 * r['db_loss_rate']:.1f} ± {100 * r['db_loss_rate_std']:.1f} | "
            f"{100 * r['false_disruption_rate']:.1f} ± {100 * r['false_disruption_rate_std']:.1f} | "
            f"{100 * r['service_uptime']:.1f} | {impacts} |"
        )
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--round", required=True)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--run-root", default="runs/validation")
    ap.add_argument("candidates", nargs="+", type=Path)
    args = ap.parse_args()
    cands = [load_candidate(p) for p in args.candidates]
    run_root = f"{args.run_root}/{args.round}"
    specs = [(n, s, o, seed, run_root) for n, s, o in cands for seed in VAL_TRAIN_SEEDS]
    specs.sort(key=lambda j: -j[1])  # longest jobs first for better packing
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        jobs = list(ex.map(run_job, *zip(*specs, strict=True)))
    rows = summarize(jobs)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"jobs": jobs, "ranking": rows}
    (RESULTS_DIR / f"{args.round}.json").write_text(json.dumps(payload, indent=2))
    md = render(rows, args.round)
    (RESULTS_DIR / f"{args.round}.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
