"""Evaluate defensive policies on live scenarios and decide (never execute) promotion.

Every metric is computed from measured outcomes of real requests against the owned
demo app. Traffic for a given (scenario, seed) is identical across policies (the
generator's randomness does not depend on the defender), so policies are compared on
**paired** episodes.

Metrics (aggregated over episodes):
- ``reward``                 mean episode return (+ bootstrap 95% CI)
- ``compromise_rate``        compromised cross-tenant reads / attack requests
- ``availability``           1 − blocked benign requests / benign requests
- ``false_disruption``       blocked benign / benign, counted only in windows with no attack
- ``no_attack_defense_duty`` share of attack-free windows in which the defense blocked at
                             least one legitimate request (reward-hacking guard)
- ``actions_per_step``       non-noop actions per step (action cost)
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from rl_defense.envs.config import NODE_NAMES
from rl_defense.envs.defense_sim import NOOP_ACTION, encode_action
from rl_defense.live.contracts import LiveTransition
from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
from rl_defense.live.scenarios import LiveScenario

PolicyFn = Callable[[np.ndarray, np.ndarray], int]
CAVEAT = (
    "Measured against the owned demo app (examples/payments-lite) in an isolated, "
    "in-process lab. Lab evidence only; not proof of real-world effectiveness (RQ-005)."
)


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


def run_policy(
    policy: PolicyFn,
    scenarios: Iterable[LiveScenario],
    app_factory,  # noqa: ANN001
    *,
    episodes: int | None = None,
    on_episode: Callable[[LiveScenario, int, list[LiveTransition]], None] | None = None,
) -> list[EpisodeMetrics]:
    rows: list[EpisodeMetrics] = []
    for sc in scenarios:
        loop = LiveDefenseLoop(
            app_factory, config=LoopConfig(horizon=sc.horizon), driver=sc.driver()
        )
        try:
            for seed in sc.seeds(episodes):
                ts = loop.run_episode(seed=seed, policy=policy)
                rows.append(episode_metrics(sc.name, seed, ts))
                if on_episode is not None:
                    on_episode(sc, seed, ts)
        finally:
            loop.close()
    return rows


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


def paired_reward_diff(a: list[EpisodeMetrics], b: list[EpisodeMetrics]) -> dict:
    """Mean and bootstrap CI of (a − b) episode return on identical (scenario, seed) pairs."""
    kb = {(x.scenario, x.seed): x.reward for x in b}
    d = np.array([x.reward - kb[(x.scenario, x.seed)] for x in a], dtype=np.float64)
    return {"mean": float(d.mean()), "ci95": bootstrap_ci(d, seed=1), "pairs": len(d)}


# ---------------------------------------------------------------------- baselines
def noop_policy(obs: np.ndarray, mask: np.ndarray) -> int:  # noqa: ARG001
    return NOOP_ACTION


def always_isolate_payments(obs: np.ndarray, mask: np.ndarray) -> int:  # noqa: ARG001
    """Naive reference: isolate payments whenever possible. Reward hacking looks like this."""
    a = encode_action("isolate", NODE_NAMES.index("payments"))
    return a if mask[a] else NOOP_ACTION


def dqn_policy(agent) -> PolicyFn:  # noqa: ANN001
    return lambda obs, mask: int(agent.greedy_action(obs, mask))


RULES_GRID = {
    "isolate_anomaly": (0.15, 0.3, 0.45, 0.6),
    "rate_limit_alerts": (0.2, 0.4, 0.6, 1.1),  # 1.1 = never (normalized alerts ≤ 1)
    "monitor_anomaly": (0.1, 0.3, 1.1),
}


def tune_rules(
    train_scenarios: list[LiveScenario],
    app_factory,  # noqa: ANN001
    *,
    episodes: int = 2,
    grid: dict[str, tuple[float, ...]] | None = None,
) -> tuple[dict, list[dict]]:
    """Grid-tune the docs/09 threshold rules on the SAME live training scenarios the
    candidate learns from (never on val/holdout), so the static-rules comparison is fair."""
    from itertools import product

    from rl_defense.baselines.policies import ThresholdParams, ThresholdRulesPolicy

    if any(s.split != "train" for s in train_scenarios):
        raise ValueError("rules must be tuned on train scenarios only")
    g = grid or RULES_GRID
    table: list[dict] = []
    for iso, rl, mon in product(g["isolate_anomaly"], g["rate_limit_alerts"], g["monitor_anomaly"]):
        pol = ThresholdRulesPolicy(ThresholdParams(iso, rl, mon))
        s = summarize(run_policy(pol.act, train_scenarios, app_factory, episodes=episodes))
        table.append(
            {
                "isolate_anomaly": iso,
                "rate_limit_alerts": rl,
                "monitor_anomaly": mon,
                "train_reward": s["reward"],
            }
        )
    best = max(table, key=lambda r: r["train_reward"])
    params = {k: best[k] for k in ("isolate_anomaly", "rate_limit_alerts", "monitor_anomaly")}
    return params, table


def rules_policy(params: dict) -> PolicyFn:
    from rl_defense.baselines.policies import ThresholdParams, ThresholdRulesPolicy

    return ThresholdRulesPolicy(ThresholdParams(**params)).act


# ---------------------------------------------------------------------- promotion gate
class PromotionCriteria(BaseModel):
    """Explicit, deterministic acceptance criteria for a candidate (configs/live/promotion.yaml)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_paired_reward_gain_ci_low: float = Field(
        0.0,
        description="lower bound of the paired 95% CI of (candidate − deployed) return must exceed this",
    )
    max_compromise_rate_vs_deployed: float = Field(
        1.0, description="candidate compromise rate ≤ this × deployed compromise rate"
    )
    min_availability: float = Field(0.85, ge=0.0, le=1.0)
    max_false_disruption: float = Field(0.25, ge=0.0, le=1.0)
    max_no_attack_defense_duty: float = Field(
        0.5, ge=0.0, le=1.0, description="reward-hacking guard: not 'isolate all the time'"
    )
    must_beat_rules: bool = True
    max_per_scenario_regression: float = Field(
        0.0,
        ge=0.0,
        description="candidate may not trail deployed by more than this on ANY holdout scenario",
    )


def promotion_decision(
    *,
    candidate: list[EpisodeMetrics],
    deployed: list[EpisodeMetrics],
    rules: list[EpisodeMetrics] | None,
    criteria: PromotionCriteria,
) -> dict:
    cs, ds = summarize(candidate), summarize(deployed)
    diff = paired_reward_diff(candidate, deployed)
    checks: list[dict] = []

    def check(name: str, passed: bool, value, threshold) -> None:  # noqa: ANN001
        checks.append(
            {"name": name, "passed": bool(passed), "value": value, "threshold": threshold}
        )

    check(
        "paired_reward_gain_ci_low",
        diff["ci95"][0] > criteria.min_paired_reward_gain_ci_low,
        diff["ci95"][0],
        f"> {criteria.min_paired_reward_gain_ci_low}",
    )
    c_comp, d_comp = cs["compromise_rate"] or 0.0, ds["compromise_rate"] or 0.0
    check(
        "compromise_rate_not_worse",
        c_comp <= criteria.max_compromise_rate_vs_deployed * d_comp + 1e-12,
        c_comp,
        f"<= {criteria.max_compromise_rate_vs_deployed} x deployed ({d_comp:.3f})",
    )
    avail = cs["availability"] if cs["availability"] is not None else 1.0
    check(
        "availability_floor",
        avail >= criteria.min_availability,
        avail,
        f">= {criteria.min_availability}",
    )
    fd = cs["false_disruption"] or 0.0
    check(
        "false_disruption_cap",
        fd <= criteria.max_false_disruption,
        fd,
        f"<= {criteria.max_false_disruption}",
    )
    duty = cs["no_attack_defense_duty"] or 0.0
    check(
        "reward_hacking_no_blanket_isolation",
        duty <= criteria.max_no_attack_defense_duty,
        duty,
        f"<= {criteria.max_no_attack_defense_duty}",
    )
    if rules is not None and criteria.must_beat_rules:
        rs = summarize(rules)
        check(
            "beats_static_rules",
            cs["reward"] > rs["reward"],
            cs["reward"],
            f"> rules ({rs['reward']:.3f})",
        )
    by_c, by_d = summarize_by_scenario(candidate), summarize_by_scenario(deployed)
    worst = min(by_c[n]["reward"] - by_d[n]["reward"] for n in by_c)
    check(
        "no_per_scenario_regression",
        worst >= -criteria.max_per_scenario_regression,
        worst,
        f">= -{criteria.max_per_scenario_regression}",
    )
    ok = all(c["passed"] for c in checks)
    return {
        "decision": "recommend_promote" if ok else "reject",
        "requires_human_approval": True,
        "checks": checks,
        "paired_reward_diff": diff,
    }
