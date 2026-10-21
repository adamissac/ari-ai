"""Summarize both preregistered arms using paired training-seed means."""

import copy
from dataclasses import fields

import numpy as np
from scipy.stats import ttest_1samp

from rl_defense.live import study
from rl_defense.live.evaluate import bootstrap_ci
from rl_defense.live.online import OnlineConfig


def summarize(reports: dict[str, list[dict]]) -> dict:
    summaries, ordered, identities = {}, {}, {}
    for arm in ("uniform", "balanced"):
        ordered[arm] = sorted(reports[arm], key=lambda r: r["online"]["seed"])
        normalized = copy.deepcopy(ordered[arm])
        identities[arm] = []
        for report in normalized:
            if report.get("balance_demo_actions", False) != (arm == "balanced"):
                raise ValueError("wrong sampling arm")
            if report["online"].get("balance_demo_actions", False) != (arm == "balanced"):
                raise ValueError("embedded training sampling arm disagrees")
            if len(report["references"]) != 2 or {r["name"] for r in report["references"]} != {
                "v8",
                "v9",
            }:
                raise ValueError("missing fixed/matched references")
            identities[arm].append(
                [
                    {k: r[k] for k in ("name", "checkpoint_sha256", "env_id")}
                    for r in report["references"]
                ]
            )
            # Matched v9 is deliberately seed-specific; fixed v8 still uses the
            # generic same-reference cohort guard. Preserve all identities separately.
            report["references"] = [r for r in report["references"] if r["name"] != "v9"]
        summaries[arm] = study.aggregate(normalized)
    left, right = ordered["uniform"], ordered["balanced"]
    if [r["git_sha"] for r in left] != [r["git_sha"] for r in right]:
        raise ValueError("arms use different source commits")
    for a, b in zip(left, right, strict=True):
        for setting in fields(OnlineConfig):
            if a["online"][setting.name] != b["online"][setting.name]:
                raise ValueError(f"arms disagree on online setting {setting.name}")
        for field in (
            "expert",
            "rules_params",
            "rules_episodes",
            "splits",
            "deployed",
            "criteria",
            "loop_overrides",
            "action_space",
            "holdout_episodes_per_scenario",
        ):
            if a[field] != b[field]:
                raise ValueError(f"arms disagree on {field}")
    if identities["uniform"] != identities["balanced"]:
        raise ValueError("arms use different reference identities")
    differences = {}
    for metric in study.METRICS:
        values = np.array(
            [
                b["policies"]["candidate"][metric] - a["policies"]["candidate"][metric]
                for a, b in zip(left, right, strict=True)
            ]
        )
        p = (
            (1.0 if values[0] == 0 else 0.0)
            if np.ptp(values) == 0
            else float(ttest_1samp(values, 0).pvalue)
        )
        differences[metric] = {
            "mean": float(values.mean()),
            "ci95": bootstrap_ci(values, n=10000, seed=1),
            "by_training_seed": values.tolist(),
            "paired_t_p_two_sided": p,
        }
    running = 0.0
    for rank, metric in enumerate(
        sorted(differences, key=lambda m: differences[m]["paired_t_p_two_sided"])
    ):
        running = max(running, min(1.0, differences[metric]["paired_t_p_two_sided"] * (6 - rank)))
        differences[metric]["holm_p"] = running
    support = (
        differences["reward"]["ci95"][0] > 0
        and summaries["balanced"]["candidate_minus_incumbent"]["reward"]["ci95"][0] > 0
        and all(
            r["decision"] == "recommend_promote"
            and r["checks"]
            and all(c["passed"] is True for c in r["checks"])
            for r in right
        )
    )
    return {
        "schema": "live-two-arm-study/0.1",
        "arms": summaries,
        "references_by_training_seed": identities,
        "balanced_minus_uniform": differences,
        "primary_hypothesis_supported": bool(support),
        "promotion_performed": False,
        "caveat": "Owned isolated payments-lite lab only; five paired seeds, no best-seed selection.",
    }
