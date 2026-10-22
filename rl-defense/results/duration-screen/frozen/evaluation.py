"""Immutable historical evaluation slice from d985e69; evidence only, never product code."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from types import SimpleNamespace

import numpy as np
from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StepOutcome(_Strict):
    """What the loop actually measured in one step window (all from real HTTP outcomes)."""

    step: int
    action: int
    action_label: str
    node: str | None
    # measured counts over the window
    attack_requests: int
    compromised_reads: int  # attack requests that really returned cross-tenant data (HTTP 200)
    benign_requests: int
    benign_blocked: int  # benign requests the defense really blocked/throttled (503/429)
    # isolate/rate_limit in force on any node during this window (observable)
    disruptive_controls_active: bool
    # traffic generator's ground truth for this window — METRICS ONLY (e.g. false
    # disruption); it never enters an observation.
    attack_active: bool
    reward: float
    reward_components: dict[str, float]
    terminated: bool
    truncated: bool


class LiveTransition(_Strict):
    """One (s, a, r, s', done) transition recorded from the live loop.

    Shapes mirror the simulator so the record is replay-buffer compatible.
    """

    obs: list[float]
    action: int
    reward: float
    next_obs: list[float]
    done: bool
    action_mask: list[bool]
    reward_components: dict[str, float]
    outcome: StepOutcome


NOOP_ACTION = 0


@dataclass
class EpisodeMetrics:
    scenario: str
    seed: int
    reward: float
    steps: int
    attack_requests: int
    compromised: int
    benign_requests: int
    benign_blocked: int
    benign_requests_no_attack: int
    benign_blocked_no_attack: int
    steps_no_attack: int
    disruptive_steps_no_attack: int
    nonnoop_actions: int


def episode_metrics(scenario: str, seed: int, ts: list[LiveTransition]) -> EpisodeMetrics:
    o = [t.outcome for t in ts]
    quiet = [x for x in o if not x.attack_active]
    return EpisodeMetrics(
        scenario=scenario,
        seed=seed,
        reward=float(sum(t.reward for t in ts)),
        steps=len(ts),
        attack_requests=sum(x.attack_requests for x in o),
        compromised=sum(x.compromised_reads for x in o),
        benign_requests=sum(x.benign_requests for x in o),
        benign_blocked=sum(x.benign_blocked for x in o),
        benign_requests_no_attack=sum(x.benign_requests for x in quiet),
        benign_blocked_no_attack=sum(x.benign_blocked for x in quiet),
        steps_no_attack=len(quiet),
        # attack-free windows in which the defense actually blocked legitimate traffic
        # (a control on a node that carries no traffic has no measurable effect)
        disruptive_steps_no_attack=sum(1 for x in quiet if x.benign_blocked > 0),
        nonnoop_actions=sum(1 for x in o if x.action != NOOP_ACTION),
    )


def _ratio(num: float, den: float) -> float | None:
    return None if den == 0 else float(num / den)


def bootstrap_ci(x: np.ndarray, n: int = 2000, seed: int = 0) -> tuple[float, float]:
    if len(x) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = rng.choice(x, size=(n, len(x)), replace=True).mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def summarize(rows: list[EpisodeMetrics]) -> dict:
    r = np.array([x.reward for x in rows], dtype=np.float64)
    tot = {
        k: sum(getattr(x, k) for x in rows)
        for k in asdict(rows[0])
        if k not in ("scenario", "seed")
    }
    blocked_frac = _ratio(tot["benign_blocked"], tot["benign_requests"])
    return {
        "episodes": len(rows),
        "reward": float(r.mean()),
        "reward_ci95": bootstrap_ci(r),
        "compromise_rate": _ratio(tot["compromised"], tot["attack_requests"]),
        "availability": None if blocked_frac is None else 1.0 - blocked_frac,
        "false_disruption": _ratio(
            tot["benign_blocked_no_attack"], tot["benign_requests_no_attack"]
        ),
        "no_attack_defense_duty": _ratio(tot["disruptive_steps_no_attack"], tot["steps_no_attack"]),
        "actions_per_step": _ratio(tot["nonnoop_actions"], tot["steps"]),
    }


def summarize_by_scenario(rows: list[EpisodeMetrics]) -> dict[str, dict]:
    names = sorted({x.scenario for x in rows})
    return {n: summarize([x for x in rows if x.scenario == n]) for n in names}


POLICIES = ("short", "long", "duration", "v6", "tuned_rules")


def paired_ratios(candidate: list[dict], reference: list[dict], metric: str) -> dict:
    """Request-weighted difference, resampling paired episodes within each scenario."""

    def keyed(rows: list[dict]) -> dict:
        result = {(r["scenario"], r["seed"]): r for r in rows}
        if len(result) != len(rows) or not rows:
            raise ValueError("missing or duplicate paired episodes")
        return result

    left, right = keyed(candidate), keyed(reference)
    if left.keys() != right.keys():
        raise ValueError("candidate and reference episode sets differ")
    numerator, denominator = (
        ("benign_blocked", "benign_requests")
        if metric == "availability"
        else ("compromised", "attack_requests")
    )
    if metric not in {"availability", "compromise_rate"}:
        raise ValueError("unknown ratio metric")
    groups = {}
    for key in sorted(left):
        a, b = left[key], right[key]
        if any(a[k] != b[k] for k in ("benign_requests", "attack_requests")):
            raise ValueError("paired traffic counts differ")
        values = [a[numerator], a[denominator], b[numerator], b[denominator]]
        if any(not np.isfinite(x) or x < 0 for x in values):
            raise ValueError("invalid traffic counters")
        if a[numerator] > a[denominator] or b[numerator] > b[denominator]:
            raise ValueError("numerator exceeds traffic denominator")
        groups.setdefault(key[0], []).append(values)
    arrays = [np.asarray(v, dtype=np.float64) for v in groups.values()]
    total = np.concatenate(arrays).sum(axis=0)
    rng = np.random.default_rng(1)
    sampled = np.zeros((10000, 4))
    for array in arrays:
        choices = rng.integers(0, len(array), size=(10000, len(array)))
        sampled += array[choices].sum(axis=1)
    undefined = int(np.count_nonzero((sampled[:, 1] == 0) | (sampled[:, 3] == 0)))
    if total[1] == 0 or total[3] == 0 or undefined:
        return {
            "mean": None,
            "ci95": None,
            "undefined_resamples": undefined,
            "reason": "undefined request fraction",
            "paired_episodes": len(left),
        }
    sign = -1 if metric == "availability" else 1
    differences = sign * (sampled[:, 0] / sampled[:, 1] - sampled[:, 2] / sampled[:, 3])
    return {
        "mean": float(sign * (total[0] / total[1] - total[2] / total[3])),
        "ci95": np.quantile(differences, [0.025, 0.975]).tolist(),
        "undefined_resamples": 0,
        "paired_episodes": len(left),
    }


def decide(rows: dict[str, list[dict]]) -> dict:
    if set(rows) != set(POLICIES):
        raise ValueError("all five fixed policies are required")
    keys = None
    for values in rows.values():
        current = {(row["scenario"], row["seed"]) for row in values}
        if len(current) != len(values) or not current or (keys is not None and current != keys):
            raise ValueError("policy episode cohorts disagree or contain duplicates")
        keys = current
    summaries = {
        name: ev.summarize([ev.EpisodeMetrics(**r) for r in values])
        for name, values in rows.items()
    }
    by_scenario = {
        name: ev.summarize_by_scenario([ev.EpisodeMetrics(**r) for r in values])
        for name, values in rows.items()
    }
    contrast = {
        metric: paired_ratios(rows["duration"], rows["v6"], metric)
        for metric in ("availability", "compromise_rate")
    }
    availability, compromise = contrast["availability"], contrast["compromise_rate"]
    per_scenario = all(
        value["compromise_rate"] is not None
        and by_scenario["v6"][name]["compromise_rate"] is not None
        and value["compromise_rate"] <= by_scenario["v6"][name]["compromise_rate"]
        for name, value in by_scenario["duration"].items()
    )
    checks = {
        "availability_gain_ci_low_positive": availability["ci95"] is not None
        and availability["ci95"][0] > 0,
        "compromise_difference_ci_high_nonpositive": compromise["ci95"] is not None
        and compromise["ci95"][1] <= 0,
        "no_scenario_compromise_increase": per_scenario,
        "availability_floor": summaries["duration"]["availability"] is not None
        and summaries["duration"]["availability"] >= 0.85,
    }
    return {
        "schema": "duration-validation-screen/0.1",
        "policies": summaries,
        "by_scenario": by_scenario,
        "duration_minus_v6": contrast,
        "checks": checks,
        "prepare_v11_preregistration": all(checks.values()),
        "promotion_performed": False,
        "scope": "Fixed heuristic policies; previously used validation, not held-out evidence or RL training.",
    }


ev = SimpleNamespace(
    EpisodeMetrics=EpisodeMetrics, summarize=summarize, summarize_by_scenario=summarize_by_scenario
)
