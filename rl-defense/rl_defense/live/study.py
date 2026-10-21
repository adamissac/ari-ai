"""Aggregate a preregistered five-seed live-lab study without selecting a best seed.

Per-run promotion reports retain their original episode-level intervals. This summary
uses training-seed means for uncertainty, and never mutates a registry or promotes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from dataclasses import fields
from pathlib import Path

import numpy as np
from scipy.stats import ttest_1samp

from rl_defense.live.evaluate import bootstrap_ci
from rl_defense.live.online import OnlineConfig

SEEDS = (0, 1, 2, 3, 4)
GATE_NAMES = frozenset(
    {
        "paired_reward_gain_ci_low",
        "compromise_rate_not_worse",
        "availability_floor",
        "false_disruption_cap",
        "reward_hacking_no_blanket_isolation",
        "beats_static_rules",
        "no_per_scenario_regression",
    }
)

METRICS = (
    "reward",
    "compromise_rate",
    "availability",
    "false_disruption",
    "no_attack_defense_duty",
    "actions_per_step",
)


def source_fingerprint(root: Path) -> str:
    repo = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    names = subprocess.run(
        ["git", "ls-files", "-z"], cwd=repo, capture_output=True, check=True
    ).stdout.split(b"\0")
    digest = hashlib.sha256()
    for name in sorted(n for n in names if n):
        path = repo / os.fsdecode(name)
        digest.update(name + b"\0")
        if path.is_symlink():
            digest.update(b"symlink\0" + os.fsencode(os.readlink(path)))
        else:
            digest.update(b"file\0")
            with path.open("rb") as stream:
                while chunk := stream.read(1 << 20):
                    digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def require_clean_source(root: Path) -> str:
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("study requires a concrete source commit")
    if subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip():
        raise ValueError("commit clean source before launching study")
    return sha


def aggregate(reports: list[dict], *, legacy_rules_episodes: dict[int, int] | None = None) -> dict:
    ordered = sorted(reports, key=lambda r: r["online"]["seed"])
    if [r["online"]["seed"] for r in ordered] != list(SEEDS):
        raise ValueError("the study requires exactly training seeds 0 through 4")
    first = ordered[0]

    def reference_ids(report: dict) -> dict:
        references = report.get("references", [])
        identities = {r["name"]: (r["checkpoint_sha256"], r["env_id"]) for r in references}
        if len(identities) != len(references):
            raise ValueError("duplicate reference policy names")
        return identities

    def teacher_budget(report: dict) -> int:
        value = report.get("rules_episodes")
        if value is None and legacy_rules_episodes is not None:
            value = legacy_rules_episodes.get(report["online"]["seed"])
        if type(value) is not int or value <= 0:
            raise ValueError("missing or invalid teacher-selection rules_episodes")
        return value

    for r in ordered:
        if not isinstance(r.get("criteria"), dict) or r["criteria"] != first["criteria"]:
            raise ValueError("study reports disagree on criteria")
        checks = r.get("checks")
        expected = (
            GATE_NAMES
            if r["criteria"].get("must_beat_rules", True)
            else GATE_NAMES - {"beats_static_rules"}
        )
        if (
            not isinstance(checks, list)
            or len(checks) != len(expected)
            or any(not isinstance(c, dict) or type(c.get("passed")) is not bool for c in checks)
            or {c.get("name") for c in checks} != expected
        ):
            raise ValueError("incomplete or invalid per-seed gate checks")
        decision = "recommend_promote" if all(c["passed"] for c in checks) else "reject"
        if r.get("decision") != decision:
            raise ValueError("per-seed gate decision disagrees with checks")
        if r.get("balance_demo_actions", False) != first.get("balance_demo_actions", False):
            raise ValueError("study reports disagree on demonstration sampling")
        if not isinstance(r.get("git_sha"), str) or not re.fullmatch(r"[0-9a-f]{40}", r["git_sha"]):
            raise ValueError("missing source commit")
        if teacher_budget(r) != teacher_budget(first):
            raise ValueError("study reports disagree on teacher-selection rules_episodes")
        for key in ("expert", "rules_params"):
            if not r.get(key) or r[key] != first.get(key):
                raise ValueError(f"missing or inconsistent teacher-selection {key}")
        expected_scenarios = set(first["splits"]["holdout"])
        actual = r.get("by_scenario", {})
        if (
            not expected_scenarios
            or set(actual) != set(r["policies"])
            or any(set(actual[name]) != expected_scenarios for name in r["policies"])
        ):
            raise ValueError("incomplete holdout scenario evidence")
        budget = r["holdout_episodes_per_scenario"]
        if (
            type(budget) is not int
            or budget <= 0
            or any(
                r["policies"][name].get("episodes") != budget * len(expected_scenarios)
                or any(
                    actual[name][scenario].get("episodes") != budget
                    for scenario in expected_scenarios
                )
                for name in r["policies"]
            )
        ):
            raise ValueError("observed episode counts differ from declared holdout budget")
        for field in fields(OnlineConfig):
            if field.name == "seed":
                continue
            if field.name not in r["online"] or field.name not in first["online"]:
                raise ValueError(f"missing online setting {field.name}")
            if r["online"][field.name] != first["online"][field.name]:
                raise ValueError(f"study reports disagree on online setting {field.name}")
        if reference_ids(r) != reference_ids(first):
            raise ValueError("study reports disagree on reference checkpoints")
        if r.get("git_sha") != first.get("git_sha"):
            raise ValueError("study reports disagree on source commit")
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
        "git_sha": first["git_sha"],
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
    ap.add_argument(
        "--legacy-rules-episodes",
        type=int,
        help="explicit historical teacher budget; verify against the saved command evidence",
    )
    args = ap.parse_args(argv)
    budgets = (
        dict.fromkeys(SEEDS, args.legacy_rules_episodes)
        if args.legacy_rules_episodes is not None
        else None
    )
    result = aggregate(
        [json.loads(p.read_text()) for p in args.reports], legacy_rules_episodes=budgets
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
