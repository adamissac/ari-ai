"""Descriptive on-policy metrics only. Never estimate unobserved policy outcomes."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

import numpy as np

from rl_defense.research.dataset import validate_episodes
from rl_defense.research.records import ResearchTransition


def totals(rows: Iterable[ResearchTransition], gamma: float) -> dict[str, float | None]:
    rs = list(rows)
    if not rs:
        raise ValueError("empty evaluation units")
    attacks = sum(r.attack_requests for r in rs)
    benign = sum(r.benign_requests for r in rs)
    quiet = [r for r in rs if not r.attack_active]
    quiet_benign = sum(r.benign_requests for r in quiet)
    known = all(r.benign_cost.value is not None for r in rs)
    quiet_known = all(r.benign_cost.value is not None for r in quiet)
    # Fraction with a measured cost, not an assumption that missing means zero.
    blocked = sum(r.benign_cost.value or 0 for r in rs) if known else None
    qblocked = sum(r.benign_cost.value or 0 for r in quiet) if quiet_known else None
    episodes = len({(r.scenario, r.seed) for r in rs})
    return {
        "attack_compromise": sum(r.compromised_reads for r in rs) / attacks if attacks else None,
        "benign_availability": 1 - blocked / benign if blocked is not None and benign else None,
        "false_disruption": qblocked / quiet_benign
        if qblocked is not None and quiet_benign
        else None,
        "mean_interventions": sum(r.action != 0 for r in rs) / episodes,
        "mean_cumulative_cost": blocked / episodes if blocked is not None else None,
        "expected_discounted_cost": sum((r.benign_cost.value or 0) * gamma**r.t for r in rs)
        / episodes
        if known
        else None,
        "mean_threat_reward": -sum(r.compromised_reads for r in rs) / episodes,
        "measured_cost_coverage": sum(r.benign_cost.value is not None for r in rs) / len(rs),
    }


def summary(
    rows: list[ResearchTransition],
    *,
    gamma: float = 1.0,
    bootstrap_seed: int = 17,
    resamples: int = 2000,
) -> dict:
    validate_episodes(rows)
    if len({r.policy for r in rows}) != 1 or len({r.split for r in rows}) != 1:
        raise ValueError("summarize one policy and split at a time")
    if not 0 < gamma <= 1 or resamples < 2:
        raise ValueError("invalid discount/bootstrap configuration")
    units: dict[int, list[ResearchTransition]] = defaultdict(list)
    for r in rows:
        # Same seed across scenarios is conservatively treated as one cluster.
        # Duplicate trajectories for a (policy,scenario,seed) already rejected above.
        units[r.seed].append(r)
    point = totals(rows, gamma)
    samples: dict[str, list[float | None]] = {k: [] for k in point}
    if len(units) >= 2:
        rng = np.random.default_rng(bootstrap_seed)
        keys = sorted(units)
        for _ in range(resamples):
            selected = [units[keys[int(i)]] for i in rng.integers(0, len(keys), len(keys))]
            # Duplicate sampled clusters must retain their multiplicity in episode means.
            numerator = {k: 0.0 for k in ("interventions", "cost", "discounted", "reward")}
            sampled = [r for block in selected for r in block]
            m = totals(sampled, gamma)
            n_eps = sum(len({(r.scenario, r.seed) for r in block}) for block in selected)
            numerator["interventions"] = sum(r.action != 0 for r in sampled)
            numerator["cost"] = sum(r.benign_cost.value or 0 for r in sampled)
            numerator["discounted"] = sum((r.benign_cost.value or 0) * gamma**r.t for r in sampled)
            numerator["reward"] = -sum(r.compromised_reads for r in sampled)
            m["mean_interventions"] = numerator["interventions"] / n_eps
            m["mean_threat_reward"] = numerator["reward"] / n_eps
            if m["mean_cumulative_cost"] is not None:
                m["mean_cumulative_cost"] = numerator["cost"] / n_eps
                m["expected_discounted_cost"] = numerator["discounted"] / n_eps
            for k in samples:
                samples[k].append(m[k])
    ci = {}
    for k, vs in samples.items():
        # Do not drop undefined bootstrap draws (e.g. all quiet/no attack).
        ci[k] = (
            [float(x) for x in np.percentile(vs, [2.5, 97.5])]
            if vs and all(v is not None for v in vs) and point[k] is not None
            else None
        )
    return {
        "episodes": len({(r.scenario, r.seed) for r in rows}),
        "independent_seed_clusters": len(units),
        "steps": len(rows),
        "metrics": point,
        "ci95": ci,
        "gamma": gamma,
        "bootstrap_seed": bootstrap_seed,
        "resamples": resamples,
    }


def report(rows: list[ResearchTransition], **kwargs) -> dict:
    policies = sorted({r.policy for r in rows})
    keys = [
        {(r.scenario, r.seed, r.scenario_hash, r.split) for r in rows if r.policy == p}
        for p in policies
    ]
    if not keys or any(k != keys[0] for k in keys[1:]):
        raise ValueError("policies lack identical scenario/seed configuration")
    return {
        p: {
            "pooled": summary([r for r in rows if r.policy == p], **kwargs),
            "by_scenario": {
                s: summary([r for r in rows if r.policy == p and r.scenario == s], **kwargs)
                for s in sorted({r.scenario for r in rows})
            },
        }
        for p in policies
    }
