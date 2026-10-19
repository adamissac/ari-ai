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

``action_space="live_v2"`` runs the loop with ``block_principal`` available. Policies built
for the 48/22 simulator layout (``dqn_policy`` of a sim checkpoint, the v1 rules) see the
first 48 features and 22 mask entries only, i.e. they cannot block principals.
``"live_v3"`` adds ``block_principal_long``; the rules then also choose a block duration
(``long_mode``) and a minimum per-principal volume (``block_min_volume``), see
:func:`tune_rules_v3`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from rl_defense.envs.config import NODE_NAMES
from rl_defense.envs.defense_sim import N_ACTIONS, NOOP_ACTION, OBS_DIM, encode_action
from rl_defense.live.actions import (
    BLOCK_PRINCIPAL_ACTION,
    BLOCK_PRINCIPAL_LONG_ACTION,
    BLOCK_TOP_PRINCIPAL_LONG_ACTION,
    FEATURE_INDEX,
    ActionSpace,
)
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
    action_space: ActionSpace = "sim",
) -> list[EpisodeMetrics]:
    rows: list[EpisodeMetrics] = []
    for sc in scenarios:
        loop = LiveDefenseLoop(
            app_factory,
            config=LoopConfig(horizon=sc.horizon, action_space=action_space),
            driver=sc.driver(),
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


def always_block_principal(obs: np.ndarray, mask: np.ndarray) -> int:  # noqa: ARG001
    """Naive v2 reference: block every flagged principal whenever possible."""
    if len(mask) > BLOCK_PRINCIPAL_ACTION and mask[BLOCK_PRINCIPAL_ACTION]:
        return BLOCK_PRINCIPAL_ACTION
    return NOOP_ACTION


def always_block_principal_long(obs: np.ndarray, mask: np.ndarray) -> int:  # noqa: ARG001
    """Naive v3 reference: block (or extend) every flagged principal for the long duration."""
    if len(mask) > BLOCK_PRINCIPAL_LONG_ACTION and mask[BLOCK_PRINCIPAL_LONG_ACTION]:
        return BLOCK_PRINCIPAL_LONG_ACTION
    return NOOP_ACTION


def always_block_top_principal_long(obs: np.ndarray, mask: np.ndarray) -> int:  # noqa: ARG001
    """Naive v3 reference: long-block the heaviest flagged principal whenever possible."""
    if len(mask) > BLOCK_TOP_PRINCIPAL_LONG_ACTION and mask[BLOCK_TOP_PRINCIPAL_LONG_ACTION]:
        return BLOCK_TOP_PRINCIPAL_LONG_ACTION
    return NOOP_ACTION


def prefix_view(policy: PolicyFn, obs_dim: int, n_actions: int) -> PolicyFn:
    """Run a narrower-layout policy inside a wider loop: it sees only its own features and
    actions (an extension's extras are invisible, its indices unchanged)."""
    return lambda obs, mask: int(policy(obs[:obs_dim], mask[:n_actions]))


def sim_view(policy: PolicyFn) -> PolicyFn:
    """Run a 48/22 simulator-layout policy inside any loop (live extras are invisible)."""
    return prefix_view(policy, OBS_DIM, N_ACTIONS)


def dqn_policy(agent) -> PolicyFn:  # noqa: ANN001
    act = lambda obs, mask: int(agent.greedy_action(obs, mask))  # noqa: E731
    if agent.n_actions == N_ACTIONS:
        return sim_view(act)
    return prefix_view(act, agent.obs_dim, agent.n_actions)


RULES_GRID = {
    "isolate_anomaly": (0.15, 0.3, 0.45, 0.6),
    "rate_limit_alerts": (0.2, 0.4, 0.6, 1.1),  # 1.1 = never (normalized alerts ≤ 1)
    "monitor_anomaly": (0.1, 0.3, 1.1),
}
# live_v2: the rules get the new control too, so "beats static rules" stays a fair bar.
# block when the hottest node's anomaly exceeds this (1.1 = never → the v1 rules).
RULES_BLOCK_GRID = (0.1, 0.2, 0.35, 0.5, 1.1)


def tune_rules(
    train_scenarios: list[LiveScenario],
    app_factory,  # noqa: ANN001
    *,
    episodes: int = 2,
    grid: dict[str, tuple[float, ...]] | None = None,
    action_space: ActionSpace = "sim",
) -> tuple[dict, list[dict]]:
    """Grid-tune the docs/09 threshold rules on the SAME live training scenarios the
    candidate learns from (never on val/holdout), so the static-rules comparison is fair.
    In ``live_v2`` the grid also covers the ``block_principal`` threshold."""
    from itertools import product

    if any(s.split != "train" for s in train_scenarios):
        raise ValueError("rules must be tuned on train scenarios only")
    g = grid or RULES_GRID
    has_block = action_space in ("live_v2", "live_v3")
    blocks = g.get("block_anomaly", RULES_BLOCK_GRID) if has_block else (None,)
    keys = ("isolate_anomaly", "rate_limit_alerts", "monitor_anomaly")
    table: list[dict] = []
    for iso, rl, mon, blk in product(*(g[k] for k in keys), blocks):
        params = dict(zip(keys, (iso, rl, mon), strict=True))
        if blk is not None:
            params["block_anomaly"] = blk
        s = summarize(
            run_policy(
                rules_policy(params),
                train_scenarios,
                app_factory,
                episodes=episodes,
                action_space=action_space,
            )
        )
        table.append({**params, "train_reward": s["reward"]})
    best = max(table, key=lambda r: r["train_reward"])
    params = {k: v for k, v in best.items() if k != "train_reward"}
    return params, table


# live_v3 stage-2 grid (base docs/09 thresholds fixed at the stage-1 optimum):
# block_anomaly as above; block_min_volume = block only if cross-tenant attempts per flagged
# principal (obs ``flagged_volume``, /6) exceed it; long_mode = when to use the long block:
#   never  - short blocks only (the v2 rules)
#   always - every block is long
#   repeat - long when a flagged principal was blocked before this episode (re-offender)
#   extend - short first; long only to extend a block whose principal is still flagged
#   outsider - long when the flagged principals read none of their own data (no customer
#            traffic to lose), short otherwise
# long_target = whom a long block covers: every flagged principal, or only the heaviest
RULES_V3_GRID = {
    "block_anomaly": (0.1, 0.2, 0.35, 0.5),
    "block_min_volume": (0.0, 0.2, 0.35, 0.5),
    "long_mode": ("never", "always", "repeat", "extend", "outsider"),
    "long_target": ("all", "top"),
}
LONG_MODES = RULES_V3_GRID["long_mode"]


def rules_policy(params: dict) -> PolicyFn:
    """docs/09 threshold rules; with ``block_anomaly`` they first try ``block_principal``,
    and with ``long_mode`` (live_v3) also ``block_principal_long``."""
    from rl_defense.baselines.policies import ThresholdParams, ThresholdRulesPolicy, node_feature
    from rl_defense.envs.config import NODE_NAMES as _NODES

    p = dict(params)
    block = p.pop("block_anomaly", None)
    min_vol = p.pop("block_min_volume", 0.0)
    long_mode = p.pop("long_mode", "never")
    long_target = p.pop("long_target", "all")
    if long_mode not in LONG_MODES or long_target not in ("all", "top"):
        raise ValueError(f"unknown long_mode/long_target {long_mode!r}/{long_target!r}")
    long_action = (
        BLOCK_TOP_PRINCIPAL_LONG_ACTION if long_target == "top" else BLOCK_PRINCIPAL_LONG_ACTION
    )
    base = sim_view(ThresholdRulesPolicy(ThresholdParams(**p)).act)
    if block is None:
        return base
    i_vol, i_rep = FEATURE_INDEX["flagged_volume"], FEATURE_INDEX["flagged_repeat"]
    i_own = FEATURE_INDEX["flagged_own_share"]

    def act(obs: np.ndarray, mask: np.ndarray) -> int:
        hottest = max(node_feature(obs, i, "anomaly_score") for i in range(len(_NODES)))
        has_long = len(mask) > BLOCK_PRINCIPAL_LONG_ACTION
        trigger = hottest > block and (not has_long or obs[i_vol] > min_vol)
        if trigger and has_long:
            short_ok = bool(mask[BLOCK_PRINCIPAL_ACTION])
            long_ok = bool(mask[long_action])
            want_long = (
                long_mode == "always"
                or (long_mode == "repeat" and obs[i_rep] > 0)
                or (long_mode == "outsider" and obs[i_own] == 0)
            )
            if long_ok and (want_long or (long_mode == "extend" and not short_ok)):
                return long_action
            if short_ok and long_mode != "always":
                return BLOCK_PRINCIPAL_ACTION
        elif trigger and len(mask) > BLOCK_PRINCIPAL_ACTION and mask[BLOCK_PRINCIPAL_ACTION]:
            return BLOCK_PRINCIPAL_ACTION
        return base(obs, mask)

    return act


def tune_rules_v3(
    train_scenarios: list[LiveScenario],
    app_factory,  # noqa: ANN001
    *,
    episodes: int = 2,
    grid: dict[str, tuple] | None = None,
    base_grid: dict[str, tuple[float, ...]] | None = None,
) -> tuple[dict, list[dict]]:
    """Two-stage tuning on TRAIN only, fixed before any v3 evaluation:
    stage 1 = the v2 grid (docs/09 thresholds × short-block threshold) in the v3 loop;
    stage 2 = the stage-1 docs/09 thresholds fixed, grid over :data:`RULES_V3_GRID`.
    Returns the best of both stages (stage-1 rows carry ``long_mode="never"``)."""
    stage1_params, stage1 = tune_rules(
        train_scenarios, app_factory, episodes=episodes, grid=base_grid, action_space="live_v3"
    )
    fixed = {
        k: stage1_params[k] for k in ("isolate_anomaly", "rate_limit_alerts", "monitor_anomaly")
    }
    g = grid or RULES_V3_GRID
    from itertools import product

    table = [{**r, "stage": 1} for r in stage1]
    for blk, vol, mode, tgt in product(
        g["block_anomaly"], g["block_min_volume"], g["long_mode"], g["long_target"]
    ):
        if mode == "never" and tgt != "all":
            continue  # long_target is irrelevant without long blocks
        params = {
            **fixed,
            "block_anomaly": blk,
            "block_min_volume": vol,
            "long_mode": mode,
            "long_target": tgt,
        }
        s = summarize(
            run_policy(
                rules_policy(params),
                train_scenarios,
                app_factory,
                episodes=episodes,
                action_space="live_v3",
            )
        )
        table.append({**params, "train_reward": s["reward"], "stage": 2})
    best = max(table, key=lambda r: r["train_reward"])
    return {k: v for k, v in best.items() if k not in ("train_reward", "stage")}, table


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
