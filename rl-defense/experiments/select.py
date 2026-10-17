"""Validation-only candidate selection (never touches held-out eval configs or seeds).

    python -m experiments.select --round r2 configs/ddqn/r2_*.yaml

Each candidate YAML holds DDQNConfig overrides plus ``steps`` and, optionally, training
options ``adversary_scale: [low, high]`` (domain randomization), ``select_every`` and
``select_start`` (in-training checkpoint selection on training configs, seeds 5000-5029). Every candidate is
trained on validation training seeds 10-12 using TRAINING configs, then scored on the
same training configs, at adversary factors ×0.5 … ×2.5 (``VAL_FACTORS``), with validation
episode seeds 2000-2099. Ranking is by the *robust* return: the mean over factors.
Held-out ``configs/eval`` and eval seeds 1000-1099 are reserved for the single final
evaluation (docs/17); stress seeds 3000-3049 are reserved for the final stress test.
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
VAL_FACTORS = (0.5, 1.0, 1.5, 2.0, 2.5)
FORBIDDEN_EPISODE_SEEDS = (*range(1000, 1100), *range(3000, 3050), *range(5000, 5030))
TRAIN_OPTION_KEYS = ("adversary_scale", "select_every", "select_start", "select_fd_penalty")
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


POSTHOC_OVERRIDES = ("disruption_margin",)  # deployment-only settings, no retraining needed


def load_candidate(path: Path) -> tuple[str, int, dict[str, Any], dict[str, Any]]:
    """Return (name, steps, DDQNConfig overrides, train() keyword options).

    A candidate with ``from_run: <round>/<candidate>`` is evaluated post hoc: the
    checkpoints of that earlier validation run are reused (same validation seeds) and only
    deployment-time overrides (``POSTHOC_OVERRIDES``) are applied. Its ``from_run`` is
    returned in the options under the key ``from_run``."""
    data = yaml.safe_load(path.read_text()) or {}
    steps = int(data.pop("steps", 200_000))
    from_run = data.pop("from_run", None)
    opts = {k: data.pop(k) for k in TRAIN_OPTION_KEYS if k in data}
    if from_run is not None:
        if set(data) - set(POSTHOC_OVERRIDES):
            raise ValueError(f"post-hoc candidate may only override {POSTHOC_OVERRIDES}")
        opts["from_run"] = str(from_run)
    if "adversary_scale" in opts:
        opts["adversary_scale"] = tuple(opts["adversary_scale"])
    return path.stem, steps, data, opts


def _nanmean(xs: list[float]) -> float:
    vals = [x for x in xs if not math.isnan(x)]
    return float(np.mean(vals)) if vals else math.nan


def _fkey(factor: float) -> str:
    return f"{factor:g}"


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
    name: str,
    steps: int,
    overrides: dict[str, Any],
    seed: int,
    run_root: str,
    train_options: dict[str, Any] | None = None,
    factors: tuple[float, ...] = VAL_FACTORS,
) -> dict[str, Any]:
    # Imports inside the worker so each process sets its own torch determinism.
    from rl_defense.agents.ddqn import DDQNConfig
    from rl_defense.envs import DefenseSimEnv, default_config_paths, load_configs
    from rl_defense.evaluate import DDQNPolicy, run_episode
    from rl_defense.stress import scaled
    from rl_defense.train import train

    assert seed not in FORBIDDEN_TRAIN_SEEDS, "seeds 0-4 are reserved for the final run"
    assert not set(VAL_EPISODE_SEEDS) & set(FORBIDDEN_EPISODE_SEEDS)
    configs = load_configs(default_config_paths("train"))
    assert all(c.split == "train" for c in configs)
    train_options = dict(train_options or {})
    from_run = train_options.pop("from_run", None)
    if from_run is None:
        run_dir = Path(run_root) / name
        manifest = train(
            configs,
            seed,
            steps,
            run_dir,
            DDQNConfig(**overrides),
            log_every=20_000,
            **train_options,
        )
        policy = DDQNPolicy(run_dir / f"ddqn_seed{seed}.pt")
    else:
        run_dir = Path(run_root).parent / from_run
        ckpt = run_dir / f"ddqn_seed{seed}.pt"
        if not ckpt.exists():
            raise FileNotFoundError(f"post-hoc candidate {name}: missing {ckpt}")
        manifest = json.loads(ckpt.with_suffix(".manifest.json").read_text())
        policy = DDQNPolicy(ckpt)
        policy.agent.config = policy.agent.config.model_copy(update=overrides)
        train_options["from_run"] = from_run
    by_factor: dict[str, dict[str, float]] = {}
    per_cfg_nominal: dict[str, dict[str, float]] = {}
    for factor in factors:
        per_cfg: dict[str, dict[str, float]] = {}
        for base in configs:
            cfg = base if factor == 1.0 else scaled(base, factor)
            assert cfg.split == "train"
            env = DefenseSimEnv(cfg)
            rows = [validate_episode(env, policy, s, run_episode) for s in VAL_EPISODE_SEEDS]
            per_cfg[base.name] = {k: _nanmean([r[k] for r in rows]) for k in METRICS}
        by_factor[_fkey(factor)] = {k: _nanmean([per_cfg[c][k] for c in per_cfg]) for k in METRICS}
        if factor == 1.0:
            per_cfg_nominal = per_cfg
    robust = {k: _nanmean([by_factor[f][k] for f in by_factor]) for k in METRICS}
    return {
        "candidate": name,
        "seed": seed,
        "steps": steps,
        "overrides": overrides,
        "train_options": {
            k: list(v) if isinstance(v, tuple) else v for k, v in (train_options or {}).items()
        },
        "adversary_scale": list(train_options["adversary_scale"])
        if train_options and train_options.get("adversary_scale")
        else None,
        "checkpoint_selection": manifest.get("checkpoint_selection"),
        "pooled": by_factor.get("1", robust),  # nominal (×1.0) metrics
        "per_config": per_cfg_nominal,
        "by_factor": by_factor,
        "robust": robust,
        "worst_factor_return": min(by_factor[f]["return"] for f in by_factor),
        "wall_clock_s": manifest["wall_clock_s"],
    }


def _stats(vals: list[float]) -> tuple[float, float]:
    mean = _nanmean(vals)
    clean = [v for v in vals if not math.isnan(v)]
    return mean, (float(np.std(clean, ddof=1)) if len(clean) > 1 else 0.0)


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
            "adversary_scale": js[0].get("adversary_scale"),
            "train_options": js[0].get("train_options", {}),
            "seeds": sorted(j["seed"] for j in js),
        }
        for k in METRICS:
            vals = [j["pooled"][k] for j in js]
            row[k], row[k + "_std"] = _stats(vals)
            row[k + "_per_seed"] = vals
        row["worst_seed_return"] = float(min(row["return_per_seed"]))
        if all("robust" in j for j in js):
            for k in ("return", "db_loss_rate", "compromise_rate", "false_disruption_rate"):
                vals = [j["robust"][k] for j in js]
                row[f"robust_{k}"], row[f"robust_{k}_std"] = _stats(vals)
                row[f"robust_{k}_per_seed"] = vals
            row["worst_seed_robust_return"] = float(min(row["robust_return_per_seed"]))
            row["worst_factor_return"] = _nanmean([j["worst_factor_return"] for j in js])
            for f in js[0]["by_factor"]:
                row[f"return_x{f}"] = _nanmean([j["by_factor"][f]["return"] for j in js])
                row[f"db_loss_x{f}"] = _nanmean([j["by_factor"][f]["db_loss_rate"] for j in js])
        rows.append(row)
    key = "robust_return" if all("robust_return" in r for r in rows) else "return"
    return sorted(rows, key=lambda r: -r[key])


def render(rows: list[dict[str, Any]], round_name: str) -> str:
    head = [
        f"# Validation round {round_name}",
        "",
        f"Training configs only; validation training seeds {sorted({s for r in rows for s in r['seeds']})}; validation "
        f"episode seeds {VAL_EPISODE_SEEDS.start}–{VAL_EPISODE_SEEDS.stop - 1} (100 per config). "
        "Mean ± std across seeds. Held-out eval configs NOT used. Overrides: "
        "`configs/ddqn/<candidate>.yaml`.",
        "",
    ]
    robust = all("robust_return" in r for r in rows)
    if robust:
        factors = [k.removeprefix("return_x") for k in rows[0] if k.startswith("return_x")]
        head += [
            f"Ranked by **robust return** = mean over adversary factors {', '.join('×' + f for f in factors)} "
            "(training configs scaled with `rl_defense.stress.scaled`).",
            "",
            "| Rank | Candidate | Steps | DR | Robust return | Worst-seed robust | Worst factor | "
            + " | ".join(f"Return ×{f}" for f in factors)
            + " | db loss ×1 / robust % | Compromise ×1 % | False disruption ×1 % | Uptime ×1 % | Impact ×1 % gw/api/auth/pay/db |",
            "|" + "---|" * (12 + len(factors)),
        ]
    else:
        head += [
            "| Rank | Candidate | Steps | Return | Worst-seed return | Compromise % | db loss % | "
            "False disruption % | Uptime % | Impact % gw/api/auth/pay/db |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    out = head
    for i, r in enumerate(rows, 1):
        impacts = "/".join(f"{100 * r['impact_' + n]:.0f}" for n in NODE_NAMES)
        if robust:
            dr = "–" if not r["adversary_scale"] else "×{:g}–{:g}".format(*r["adversary_scale"])
            out.append(
                f"| {i} | {r['candidate']} | {r['steps']:,} | {dr} | "
                f"{r['robust_return']:.1f} ± {r['robust_return_std']:.1f} | "
                f"{r['worst_seed_robust_return']:.1f} | {r['worst_factor_return']:.1f} | "
                + " | ".join(f"{r['return_x' + f]:.1f}" for f in factors)
                + f" | {100 * r['db_loss_rate']:.1f} / {100 * r['robust_db_loss_rate']:.1f} | "
                f"{100 * r['compromise_rate']:.1f} ± {100 * r['compromise_rate_std']:.1f} | "
                f"{100 * r['false_disruption_rate']:.1f} ± {100 * r['false_disruption_rate_std']:.1f} | "
                f"{100 * r['service_uptime']:.1f} | {impacts} |"
            )
        else:
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
    ap.add_argument(
        "--seeds",
        type=lambda s: [int(x) for x in s.split(",")],
        default=list(VAL_TRAIN_SEEDS),
        help="comma-separated validation training seeds, e.g. 10,11,12,13,14",
    )
    ap.add_argument("candidates", nargs="+", type=Path)
    args = ap.parse_args()
    if set(args.seeds) & set(FORBIDDEN_TRAIN_SEEDS):
        ap.error("validation seeds must not include the final training seeds 0-4")
    cands = [load_candidate(p) for p in args.candidates]
    run_root = f"{args.run_root}/{args.round}"
    specs = [(n, s, o, seed, run_root, opts) for n, s, o, opts in cands for seed in args.seeds]
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
