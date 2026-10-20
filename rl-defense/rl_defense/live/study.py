"""Aggregate a preregistered five-seed live-lab study without selecting a best seed.

Per-run promotion reports retain their original episode-level intervals. This summary
uses training-seed means for uncertainty, and never mutates a registry or promotes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import ttest_1samp

from rl_defense.live.evaluate import bootstrap_ci

SEEDS = (0, 1, 2, 3, 4)
METRICS = (
    "reward",
    "compromise_rate",
    "availability",
    "false_disruption",
    "no_attack_defense_duty",
    "actions_per_step",
)


def aggregate(reports: list[dict]) -> dict:
    ordered = sorted(reports, key=lambda r: r["online"]["seed"])
    if [r["online"]["seed"] for r in ordered] != list(SEEDS):
        raise ValueError("the study requires exactly training seeds 0 through 4")
    first = ordered[0]
    for r in ordered:
        for key in ("splits", "criteria", "loop_overrides", "action_space", "deployed"):
            if r[key] != first[key]:
                raise ValueError(f"study reports disagree on {key}")
        if set(r["policies"]) != set(first["policies"]):
            raise ValueError("study reports must contain identical policies")
        if r["holdout_episodes_per_scenario"] != first["holdout_episodes_per_scenario"]:
            raise ValueError("study reports must have identical evaluation budgets")
    policies = {}
    for name in first["policies"]:
        metrics = {}
        for metric in METRICS:
            values = [r["policies"][name][metric] for r in ordered]
            if any(v is None or not np.isfinite(v) for v in values):
                raise ValueError(f"undefined {name}.{metric} is not a passing result")
            values = np.asarray(values, dtype=float)
            metrics[metric] = {
                "mean": float(values.mean()),
                "ci95": bootstrap_ci(values, n=10_000, seed=0),
                "by_training_seed": values.tolist(),
            }
        policies[name] = metrics
    by_scenario = {}
    for name in first["policies"]:
        by_scenario[name] = {}
        for scenario in first.get("by_scenario", {}).get(name, {}):
            by_scenario[name][scenario] = {}
            for metric in METRICS:
                values = np.array(
                    [r["by_scenario"][name][scenario][metric] for r in ordered], dtype=float
                )
                if not np.isfinite(values).all():
                    raise ValueError(f"undefined scenario metric {name}.{scenario}.{metric}")
                by_scenario[name][scenario][metric] = {
                    "mean": float(values.mean()),
                    "ci95": bootstrap_ci(values, n=10_000, seed=0),
                    "by_training_seed": values.tolist(),
                }
    differences = {}
    for metric in METRICS:
        d = np.array(
            [
                r["policies"]["candidate"][metric] - r["policies"]["deployed"][metric]
                for r in ordered
            ]
        )
        # A constant nonzero difference has no sampling variance. State the limit
        # explicitly instead of relying on scipy's precision-loss warning.
        p = (1.0 if d[0] == 0 else 0.0) if np.ptp(d) == 0 else float(ttest_1samp(d, 0).pvalue)
        differences[metric] = {
            "mean": float(d.mean()),
            "ci95": bootstrap_ci(d, n=10_000, seed=1),
            "by_training_seed": d.tolist(),
            "paired_t_p_two_sided": p,
        }
    # Holm correction across all six predeclared metrics; do not pick a metric later.
    running = 0.0
    for rank, metric in enumerate(
        sorted(METRICS, key=lambda m: differences[m]["paired_t_p_two_sided"])
    ):
        running = max(
            running, min(1.0, differences[metric]["paired_t_p_two_sided"] * (len(METRICS) - rank))
        )
        differences[metric]["holm_p"] = running
    return {
        "schema": "live-five-seed-study/0.1",
        "training_seeds": list(SEEDS),
        "caveat": first["caveat"],
        "deployed": first["deployed"],
        "splits": first["splits"],
        "criteria": first["criteria"],
        "holdout_episodes_per_scenario": first["holdout_episodes_per_scenario"],
        "policies": policies,
        "by_scenario": by_scenario,
        "candidate_minus_incumbent": differences,
        "per_seed_gate": [
            {"seed": r["online"]["seed"], "decision": r["decision"], "checks": r["checks"]}
            for r in ordered
        ],
        "promotion_performed": False,
        "interpretation": "Uncertainty is across five training-seed means; paired t tests use n=5. No best seed is selected. Per-seed gate intervals remain episode-level and do not replace this summary.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("reports", nargs=5, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    result = aggregate([json.loads(p.read_text()) for p in args.reports])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
