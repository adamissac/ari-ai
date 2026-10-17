"""DefenseSimEnv-v0: an abstract, simulated cyber-defense environment.

The adversary progresses through abstract stages per node
(none -> foothold -> escalated -> impact). It does not model any real attack
technique. The defender only sees noisy alert signals and asset context; the
hidden adversary stage never enters the observation (see ``_observe``).

Spec: docs/09_RL_DEFENSE_SYSTEM.md. Evaluation: docs/17_RL_EVALUATION_PROTOCOL.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from rl_defense.envs.config import NODE_NAMES, ScenarioConfig

N_NODES = len(NODE_NAMES)
STAGE_NONE, STAGE_FOOTHOLD, STAGE_ESCALATED, STAGE_IMPACT = 0, 1, 2, 3
DB_INDEX = NODE_NAMES.index("db")

# Action layout: 0 = noop; then per node 4 actions; last = escalate_to_human.
NODE_ACTIONS: tuple[str, ...] = (
    "raise_monitoring",
    "rate_limit",
    "isolate",
    "request_reassessment",
)
N_ACTIONS = 1 + N_NODES * len(NODE_ACTIONS) + 1
ESCALATE_ACTION = N_ACTIONS - 1
NOOP_ACTION = 0
DISRUPTIVE = frozenset({"rate_limit", "isolate"})

# Per-node observation features (all observable, normalized to [0, 1]).
NODE_FEATURES: tuple[str, ...] = (
    "alert_rate",
    "anomaly_score",
    "criticality",
    "exposed",
    "finding_severity",
    "monitoring_level",
    "rate_limited",
    "isolated",
    "reassessment_pending",
)
GLOBAL_FEATURES: tuple[str, ...] = ("time_fraction", "escalations_remaining", "escalation_pending")
OBS_DIM = N_NODES * len(NODE_FEATURES) + len(GLOBAL_FEATURES)
ALERT_WINDOW = 5
ALERT_NORM = 10.0  # alerts/step that maps to 1.0
NEG_INF_MASK = -1e18  # score for masked-out actions


def decode_action(action: int) -> tuple[str, int | None]:
    """Return (action_name, node_index or None)."""
    if action == NOOP_ACTION:
        return "noop", None
    if action == ESCALATE_ACTION:
        return "escalate_to_human", None
    idx = action - 1
    return NODE_ACTIONS[idx % len(NODE_ACTIONS)], idx // len(NODE_ACTIONS)


def encode_action(name: str, node: int | None = None) -> int:
    if name == "noop":
        return NOOP_ACTION
    if name == "escalate_to_human":
        return ESCALATE_ACTION
    assert node is not None
    return 1 + node * len(NODE_ACTIONS) + NODE_ACTIONS.index(name)


def action_label(action: int) -> str:
    name, node = decode_action(action)
    return name if node is None else f"{name}:{NODE_NAMES[node]}"


@dataclass
class _Observable:
    """State the defender can legitimately know."""

    alert_history: np.ndarray  # (ALERT_WINDOW, N) alerts per step
    anomaly: np.ndarray  # (N,)
    finding_severity: np.ndarray  # (N,)
    monitoring_level: np.ndarray  # (N,) int
    monitoring_timer: np.ndarray
    rate_limit_timer: np.ndarray
    isolate_timer: np.ndarray
    reassess_timer: np.ndarray  # 0 = none pending
    escalations_used: int = 0
    escalation_timer: int = 0
    t: int = 0


@dataclass
class _Hidden:
    """Adversary state. Never observed by the agent."""

    stage: np.ndarray  # (N,) int
    first_foothold_t: int | None = None
    contained_streak: int = 0
    containment_t: int | None = None
    ever_impact: bool = False
    impact_nodes: set[int] = field(default_factory=set)


class DefenseSimEnv(gym.Env[np.ndarray, np.int64]):
    metadata = {"render_modes": ["ansi"]}

    def __init__(self, config: ScenarioConfig, render_mode: str | None = None) -> None:
        super().__init__()
        self.config = config
        self.render_mode = render_mode
        self.observation_space = spaces.Box(0.0, 1.0, shape=(OBS_DIM,), dtype=np.float32)
        self.action_space = spaces.Discrete(N_ACTIONS)
        self._criticality = np.array([n.criticality for n in config.nodes], dtype=np.float64)
        self._exposed = np.array([n.exposed for n in config.nodes], dtype=bool)
        self._initial_severity = np.array([n.finding_severity for n in config.nodes])
        self._parents: list[list[int]] = [[] for _ in range(N_NODES)]
        for src, dst in config.edges:
            self._parents[NODE_NAMES.index(dst)].append(NODE_NAMES.index(src))
        self._obs_state: _Observable | None = None
        self._hidden: _Hidden | None = None

    # ------------------------------------------------------------------ API
    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        self._obs_state = _Observable(
            alert_history=np.zeros((ALERT_WINDOW, N_NODES)),
            anomaly=np.zeros(N_NODES),
            finding_severity=self._initial_severity.copy(),
            monitoring_level=np.zeros(N_NODES, dtype=np.int64),
            monitoring_timer=np.zeros(N_NODES, dtype=np.int64),
            rate_limit_timer=np.zeros(N_NODES, dtype=np.int64),
            isolate_timer=np.zeros(N_NODES, dtype=np.int64),
            reassess_timer=np.zeros(N_NODES, dtype=np.int64),
        )
        self._hidden = _Hidden(stage=np.zeros(N_NODES, dtype=np.int64))
        self._emit_signals()
        return self._observe(), self._info(action=None, events={})

    def step(self, action: Any) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        assert self._obs_state is not None and self._hidden is not None, "call reset() first"
        o, h, cfg = self._obs_state, self._hidden, self.config
        action = int(action)
        mask = self.action_masks()
        invalid = not (0 <= action < N_ACTIONS) or not mask[action]
        applied = NOOP_ACTION if invalid else action
        name, node = decode_action(applied)
        events: dict[str, Any] = {"invalid_action": invalid}

        reward = 0.0
        rp = cfg.reward
        if invalid:
            reward -= rp.c_invalid
        if applied != NOOP_ACTION:
            reward -= rp.c_action
        self._apply_action(name, node, events)
        if name == "escalate_to_human":
            reward -= rp.c_escalate

        # Disruption from active rate-limits/isolations: costlier on benign nodes.
        disruption = 0.0
        for i in range(N_NODES):
            benign = h.stage[i] == STAGE_NONE
            if o.isolate_timer[i] > 0:
                disruption += self._criticality[i] * (1.0 if benign else 0.3)
            elif o.rate_limit_timer[i] > 0:
                disruption += 0.3 * self._criticality[i] * (1.0 if benign else 0.3)
        reward -= rp.c_disrupt * disruption

        contained = self._resolve_delayed_effects(events)
        progressed = self._advance_adversary(events)
        reward -= rp.c_progress * float(np.dot(progressed, self._criticality))
        reward += rp.c_contain * float(np.dot(contained, self._criticality))

        impact_mask = h.stage == STAGE_IMPACT
        reward -= rp.c_impact * float(np.dot(impact_mask, self._criticality))
        if impact_mask.any():
            h.ever_impact = True
            h.impact_nodes |= set(np.flatnonzero(impact_mask).tolist())

        self._tick_timers()
        o.t += 1
        self._update_containment()
        self._emit_signals()

        terminated = bool(h.stage[DB_INDEX] == STAGE_IMPACT)
        if terminated:
            # Ending early must not be cheaper than surviving: charge the per-step impact
            # cost for the remaining horizon as if the damage continued, plus a fixed penalty.
            remaining = cfg.horizon - o.t
            reward -= rp.c_terminal + remaining * rp.c_impact * float(
                np.dot(impact_mask, self._criticality)
            )
        truncated = bool(o.t >= cfg.horizon and not terminated)
        events.update(
            {
                "disruption": disruption,
                "progressed": int(progressed.sum()),
                "contained": int(contained.sum()),
                "disruptive_on_benign": bool(
                    name in DISRUPTIVE and node is not None and events.get("target_stage") == 0
                ),
            }
        )
        return self._observe(), float(reward), terminated, truncated, self._info(applied, events)

    def action_masks(self) -> np.ndarray:
        """Boolean mask of valid actions given *observable* state only."""
        o, d = self._obs_state, self.config.defense
        assert o is not None
        mask = np.zeros(N_ACTIONS, dtype=bool)
        mask[NOOP_ACTION] = True
        for i in range(N_NODES):
            isolated = o.isolate_timer[i] > 0
            mask[encode_action("raise_monitoring", i)] = (
                o.monitoring_level[i] < d.max_monitoring_level
            )
            mask[encode_action("rate_limit", i)] = not isolated and o.rate_limit_timer[i] == 0
            mask[encode_action("isolate", i)] = not isolated
            mask[encode_action("request_reassessment", i)] = (
                o.reassess_timer[i] == 0 and o.finding_severity[i] > d.reassessment_severity_after
            )
        mask[ESCALATE_ACTION] = o.escalations_used < d.max_escalations and o.escalation_timer == 0
        return mask

    def render(self) -> str | None:
        if self.render_mode != "ansi" or self._obs_state is None:
            return None
        o = self._obs_state
        rows = [f"t={o.t}"]
        for i, n in enumerate(NODE_NAMES):
            rows.append(
                f"{n:9s} alerts={o.alert_history[-1, i]:4.0f} anomaly={o.anomaly[i]:.2f} "
                f"mon={o.monitoring_level[i]} rl={o.rate_limit_timer[i]} iso={o.isolate_timer[i]}"
            )
        return "\n".join(rows)

    # ------------------------------------------------------------- internals
    def _apply_action(self, name: str, node: int | None, events: dict[str, Any]) -> None:
        o, h, d = self._obs_state, self._hidden, self.config.defense
        assert o is not None and h is not None
        if node is not None:
            events["target_stage"] = int(h.stage[node])  # for metrics only (info), not observation
        if name == "raise_monitoring":
            o.monitoring_level[node] += 1
            o.monitoring_timer[node] = d.monitoring_duration
        elif name == "rate_limit":
            o.rate_limit_timer[node] = d.effect_duration
        elif name == "isolate":
            o.isolate_timer[node] = d.effect_duration
            o.rate_limit_timer[node] = 0
        elif name == "request_reassessment":
            o.reassess_timer[node] = d.reassessment_delay
        elif name == "escalate_to_human":
            o.escalations_used += 1
            o.escalation_timer = d.escalation_delay

    def _resolve_delayed_effects(self, events: dict[str, Any]) -> np.ndarray:
        """Isolation eviction, finished reassessments and escalations. Returns contained mask."""
        o, h, d = self._obs_state, self._hidden, self.config.defense
        assert o is not None and h is not None
        rng = self.np_random
        contained = np.zeros(N_NODES, dtype=bool)
        for i in range(N_NODES):
            if o.isolate_timer[i] > 0 and h.stage[i] > STAGE_NONE and h.stage[i] < STAGE_IMPACT:
                if rng.random() < d.isolate_clean_prob:
                    h.stage[i] = STAGE_NONE
                    contained[i] = True
            if o.reassess_timer[i] == 1:  # completes this step
                o.finding_severity[i] = min(o.finding_severity[i], d.reassessment_severity_after)
        if o.escalation_timer == 1:
            # A human investigates the node with the highest current anomaly signal.
            target = int(np.argmax(o.anomaly))
            events["escalation_target"] = NODE_NAMES[target]
            if (
                STAGE_NONE < h.stage[target] < STAGE_IMPACT
                and rng.random() < d.escalation_success_prob
            ):
                h.stage[target] = STAGE_NONE
                contained[target] = True
        return contained

    def _advance_adversary(self, events: dict[str, Any]) -> np.ndarray:
        o, h, cfg = self._obs_state, self._hidden, self.config
        assert o is not None and h is not None
        a, d = cfg.adversary, cfg.defense
        rng = self.np_random
        before = h.stage.copy()
        for i in range(N_NODES):
            if o.isolate_timer[i] > 0:
                continue  # isolated nodes neither progress nor spread
            modifier = 1.0 + a.severity_weight * o.finding_severity[i]
            if o.rate_limit_timer[i] > 0:
                modifier *= d.rate_limit_factor
            s = before[i]
            if s == STAGE_NONE:
                p = a.entry_prob if self._exposed[i] else 0.0
                active_parents = [
                    j
                    for j in self._parents[i]
                    if before[j] >= STAGE_ESCALATED and o.isolate_timer[j] == 0
                ]
                if active_parents:
                    p = 1.0 - (1.0 - p) * (1.0 - a.lateral_prob) ** len(active_parents)
                if rng.random() < min(1.0, p * modifier):
                    h.stage[i] = STAGE_FOOTHOLD
            elif s == STAGE_FOOTHOLD:
                if rng.random() < min(1.0, a.escalate_prob * modifier):
                    h.stage[i] = STAGE_ESCALATED
            elif s == STAGE_ESCALATED:
                if rng.random() < min(1.0, a.impact_prob * modifier):
                    h.stage[i] = STAGE_IMPACT
        progressed = h.stage > before
        if progressed.any() and h.first_foothold_t is None and (h.stage >= STAGE_FOOTHOLD).any():
            h.first_foothold_t = o.t
        return progressed

    def _tick_timers(self) -> None:
        o = self._obs_state
        assert o is not None
        for timer in (o.rate_limit_timer, o.isolate_timer, o.reassess_timer):
            np.subtract(timer, 1, out=timer, where=timer > 0)
        # Monitoring decays one level per `monitoring_duration` steps without a new raise.
        active = o.monitoring_timer > 0
        o.monitoring_timer[active] -= 1
        expired = active & (o.monitoring_timer == 0)
        o.monitoring_level[expired] -= 1
        o.monitoring_timer[expired & (o.monitoring_level > 0)] = (
            self.config.defense.monitoring_duration
        )
        if o.escalation_timer > 0:
            o.escalation_timer -= 1

    def _update_containment(self) -> None:
        h, o = self._hidden, self._obs_state
        assert h is not None and o is not None
        if h.first_foothold_t is None or h.containment_t is not None:
            return
        if (h.stage == STAGE_NONE).all():
            h.contained_streak += 1
            if h.contained_streak >= 10:
                h.containment_t = o.t - 10
        else:
            h.contained_streak = 0

    def _emit_signals(self) -> None:
        """Generate noisy alerts from hidden stage + benign noise. Only signals are kept."""
        o, h, sp = self._obs_state, self._hidden, self.config.signals
        assert o is not None and h is not None
        rng = self.np_random
        detect = 1.0 + sp.monitoring_gain * o.monitoring_level
        mean = sp.benign_alert_rate + sp.stage_alert_rate * h.stage * detect
        bursts = rng.random(N_NODES) < sp.benign_burst_prob
        mean = mean + bursts * sp.stage_alert_rate * 2.0
        alerts = rng.poisson(mean).astype(np.float64)
        o.alert_history = np.vstack([o.alert_history[1:], alerts])
        excess = (alerts - sp.benign_alert_rate) / ALERT_NORM
        noise = rng.normal(0.0, sp.anomaly_noise, N_NODES)
        o.anomaly = np.clip(0.7 * o.anomaly + 0.3 * (excess + noise), 0.0, 1.0)

    def _observe(self) -> np.ndarray:
        """Build the observation from observable state ONLY (no access to ``self._hidden``)."""
        o, d, cfg = self._obs_state, self.config.defense, self.config
        assert o is not None
        per_node = np.stack(
            [
                np.clip(o.alert_history.mean(axis=0) / ALERT_NORM, 0.0, 1.0),
                o.anomaly,
                self._criticality,
                self._exposed.astype(np.float64),
                o.finding_severity,
                o.monitoring_level / d.max_monitoring_level,
                (o.rate_limit_timer > 0).astype(np.float64),
                (o.isolate_timer > 0).astype(np.float64),
                (o.reassess_timer > 0).astype(np.float64),
            ],
            axis=1,
        )
        glob = np.array(
            [
                o.t / cfg.horizon,
                1.0 - o.escalations_used / max(1, d.max_escalations),
                float(o.escalation_timer > 0),
            ]
        )
        return np.clip(np.concatenate([per_node.ravel(), glob]), 0.0, 1.0).astype(np.float32)

    def _info(self, action: int | None, events: dict[str, Any]) -> dict[str, Any]:
        """Info is for logging/metrics. Agents must use only obs and ``action_mask``."""
        o, h = self._obs_state, self._hidden
        assert o is not None and h is not None
        return {
            "action_mask": self.action_masks(),
            "t": o.t,
            "action": None if action is None else action_label(action),
            "events": events,
            # Ground truth for evaluation metrics only — never fed to the policy.
            "metrics": {
                "stages": h.stage.tolist(),
                "ever_impact": h.ever_impact,
                "first_foothold_t": h.first_foothold_t,
                "containment_t": h.containment_t,
            },
        }
