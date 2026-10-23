"""Research-only Gymnasium finite-resource model; no external control or training hook."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import gymnasium as gym
import numpy as np
from numpy.typing import NDArray

from rl_defense.research.resource.service import Arrival, Config, Service, Window
from rl_defense.research.resource.workload import FAMILIES, Family, window

OBS_VERSION = "resource-observation/0.1"
ACTION_VERSION = "resource-actions/0.1"
ACTIONS = ("noop", "rate_limit_route", "rate_limit_source")
BASE_FEATURES = (
    "arrivals",
    "accepted",
    "rejected",
    "completed",
    "timeouts",
    "queue_depth",
    "inflight",
    "latency_mean",
    "utilization",
    "limit_denials",
    "capacity_denials",
    "active_route",
    "active_source",
    "pending_windows",
    "remaining_windows",
    "cooldown_windows",
    "budget_remaining",
    "time_remaining",
)
FEATURES = (
    *BASE_FEATURES,
    *(f"source_arrivals_{i}" for i in range(4)),
    *(f"source_work_{i}" for i in range(4)),
    *(f"route_arrivals_{i}" for i in range(2)),
    *(f"route_work_{i}" for i in range(2)),
    *(f"controlled_source_{i}" for i in range(4)),
    "intervention_count",
)
INDEX = {f: i for i, f in enumerate(FEATURES)}
OBS_DIM = len(FEATURES) * 2 + len(ACTIONS)


@dataclass(frozen=True)
class Control:
    kind: str
    target: int
    issued: int
    start: int
    end: int
    cooldown_until: int


class ResourceEnv(gym.Env[NDArray[np.float32], np.int64]):
    """Virtual-clock FIFO service. Observations are partial, not proven Markov.

    Sequence cutoffs order snapshot < action < events < next snapshot. Ground-truth
    labels appear in reward/cost evaluation and traces only, never observations.
    Controls share one actuator and budget; neither can bypass authorization.
    """

    metadata: dict[str, list[str]] = {"render_modes": []}

    def __init__(
        self,
        config: Config | None = None,
        *,
        family: Family = "stable",
        script: tuple[tuple[Arrival, ...], ...] | None = None,
        telemetry: bool = True,
        fixed_static: bool = False,
    ) -> None:
        super().__init__()
        self.config = config or Config()
        if family not in FAMILIES or type(telemetry) is not bool or type(fixed_static) is not bool:
            raise ValueError("known development family and explicit telemetry flag required")
        if script is not None and len(script) != self.config.horizon:
            raise ValueError("script must specify exactly the episode horizon")
        self.family, self._script, self.telemetry = family, script, telemetry
        self.fixed_static = fixed_static
        self.observation_space = gym.spaces.Box(0.0, 1.0, shape=(OBS_DIM,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(len(ACTIONS))
        self.service = Service(self.config)
        self.index = 0
        self.used = 0
        self.control: Control | None = None
        self.ledger: list[dict[str, Any]] = []
        self.attempts: list[dict[str, Any]] = []
        self.last: Window | None = None
        self.cutoff = 0
        self._ready = False
        self._ended = False

    def _current(self) -> Control | None:
        control = self.control
        return control if control is not None and self.index < control.end else None

    def _source_target(self) -> int | None:
        if self.last is None or not self.telemetry or not self.last.offered:
            return None
        # Work actually consumed in the completed window; tie-break lowest slot.
        counts = self.last.source_work if any(self.last.source_work) else self.last.source_arrivals
        return int(np.argmax(counts))

    def action_masks(self) -> NDArray[np.bool_]:
        free = self._current() is None and (
            self.control is None or self.index >= self.control.cooldown_until
        )
        available = (
            self._ready
            and not self._ended
            and self.telemetry
            and not self.fixed_static
            and self.used < self.config.application_budget
            and free
            and self.index + self.config.delay < self.config.horizon
        )
        return np.array(
            [True, available, available and self._source_target() is not None], dtype=bool
        )

    def _observe(self) -> NDArray[np.float32]:
        c = self.config
        values = dict.fromkeys(FEATURES, 0.0)
        known = dict.fromkeys(FEATURES, True)
        previous = self.last if self.telemetry else None
        measured = (
            *BASE_FEATURES[:5],
            "latency_mean",
            "utilization",
            "limit_denials",
            "capacity_denials",
            *(f"source_arrivals_{i}" for i in range(4)),
            *(f"source_work_{i}" for i in range(4)),
            *(f"route_arrivals_{i}" for i in range(2)),
            *(f"route_work_{i}" for i in range(2)),
        )
        if previous is None:
            for name in measured:
                known[name] = False
        else:
            scale = 64 + c.workers + c.queue_capacity
            for name, count in (
                ("arrivals", previous.offered),
                ("accepted", previous.accepted),
                ("rejected", previous.limit_denials + previous.capacity_denials),
                ("completed", previous.completed),
                ("timeouts", previous.timeouts),
                ("limit_denials", previous.limit_denials),
                ("capacity_denials", previous.capacity_denials),
            ):
                values[name] = count / scale
            known["latency_mean"] = previous.completed > 0
            values["latency_mean"] = (
                previous.latency_sum / max(1, previous.completed) / c.deadline_ticks
            )
            values["utilization"] = (previous.work + previous.overhead) / (
                c.workers * c.window_ticks
            )
            for kind in ("source", "route"):
                for i, count in enumerate(getattr(previous, f"{kind}_arrivals")):
                    values[f"{kind}_arrivals_{i}"] = count / 64
                for i, count in enumerate(getattr(previous, f"{kind}_work")):
                    values[f"{kind}_work_{i}"] = count / (c.workers * c.window_ticks)
        values["queue_depth"] = max(0, len(self.service.pending) - c.workers) / c.queue_capacity
        values["inflight"] = len(self.service.pending) / (c.workers + c.queue_capacity)
        current = self._current()
        if current is not None:
            pending = max(0, current.start - self.index)
            active = pending == 0
            values[f"active_{current.kind}"] = float(active)
            values["pending_windows"] = pending / c.delay
            values["remaining_windows"] = (current.end - max(self.index, current.start)) / (
                c.horizon if self.fixed_static else c.duration
            )
            if current.kind == "source":
                values[f"controlled_source_{current.target}"] = 1.0
        if self.control is not None:
            # Cooldown starts at end; pending/active duration has its own channel.
            values["cooldown_windows"] = max(
                0, self.control.cooldown_until - max(self.index, self.control.end)
            ) / max(1, c.cooldown)
        values["budget_remaining"] = (c.application_budget - self.used) / max(
            1, c.application_budget
        )
        values["intervention_count"] = self.used / max(1, c.application_budget)
        if self.fixed_static:
            known["budget_remaining"] = False  # reference is outside the adaptive cap
            values["budget_remaining"] = 0.0
            values["intervention_count"] = float(self.index > 0)
        values["time_remaining"] = (c.horizon - self.index) / c.horizon
        out = np.array(
            [
                *(values[f] for f in FEATURES),
                *(float(known[f]) for f in FEATURES),
                *self.action_masks().astype(float),
            ],
            dtype=np.float32,
        )
        if not self.observation_space.contains(out):
            raise AssertionError("observation normalization contract failed")
        return out

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[NDArray[np.float32], dict[str, Any]]:
        super().reset(seed=seed)
        self.service = Service(self.config)
        self.index = self.used = 0
        self.control = None
        self.ledger, self.attempts = [], []
        self.last = None
        self._ready, self._ended = True, False
        self.cutoff = 0
        if self.fixed_static:
            self.control = Control("route", 1, 0, 0, self.config.horizon, self.config.horizon)
            self.ledger.append({"event": "static_reference", **asdict(self.control)})
        return self._observe(), {"observation_cutoff_seq": self.cutoff, "schema": OBS_VERSION}

    def step(
        self, action: int | np.int64
    ) -> tuple[NDArray[np.float32], float, bool, bool, dict[str, Any]]:
        if not self._ready or self._ended:
            raise RuntimeError("reset required; episode has ended or not started")
        mask = self.action_masks()
        valid = type(action) in (int, np.int64, np.int32) and 0 <= action < 3 and mask[action]
        self.attempts.append(
            {
                "window": self.index,
                "proposal": int(action)
                if type(action) in (int, np.int64, np.int32)
                else str(action),
                "accepted": bool(valid),
            }
        )
        if not valid:
            raise ValueError("invalid or infeasible research action")
        before = self.service.metrics()
        old_cutoff = self.cutoff
        self.service.sequence += 1
        action_seq = self.service.sequence
        overhead = self.config.apply_overhead if self.fixed_static and self.index == 0 else 0
        if action:
            target = 1 if action == 1 else self._source_target()
            assert target is not None
            start = self.index + self.config.delay
            end = start + self.config.duration
            self.control = Control(
                "route" if action == 1 else "source",
                target,
                self.index,
                start,
                end,
                end + self.config.cooldown,
            )
            self.used += 1
            overhead = self.config.apply_overhead
            self.ledger.append(
                {"event": "scheduled", **asdict(self.control), "action_seq": action_seq}
            )
        active = self._current()
        if active is not None and self.index < active.start:
            active = None
        offered = (
            self._script[self.index]
            if self._script is not None
            else window(self.np_random, self.config, self.family, self.index)
        )
        self.last = self.service.advance(
            offered,
            limit_kind=active.kind if active else None,
            target=active.target if active else None,
            quota=(self.config.route_quota if active.kind == "route" else self.config.source_quota)
            if active
            else 0,
            overhead=overhead,
        )
        if active:
            self.ledger.append({"event": "active", "window": self.index, **asdict(active)})
        after = self.service.metrics()
        costs = {
            name: int(after[key] or 0) - int(before[key] or 0)
            for name, key in (
                ("legitimate_rate_denials", "legitimate_rate_denied"),
                ("legitimate_capacity_denials", "legitimate_capacity_denied"),
                ("legitimate_timeouts", "legitimate_timeouts"),
                ("legitimate_latency_sum", "legitimate_latency_sum"),
            )
        }
        costs.update(
            applications=int(action != 0 or (self.fixed_static and self.index == 0)),
            active_ticks=self.config.window_ticks if active else 0,
            overhead_units=overhead,
        )
        reward = -(int(after["adversarial_work"] or 0) - int(before["adversarial_work"] or 0))
        self.index += 1
        if self.control is not None and self.index == self.control.end:
            self.ledger.append({"event": "expired", "window": self.index, **asdict(self.control)})
        self._ended = self.index >= self.config.horizon
        if self._ended and self._current() is not None:
            assert self.control is not None
            self.ledger.append(
                {"event": "episode_stop", "window": self.index, **asdict(self.control)}
            )
            self.control = None
        self.service.sequence += 1
        self.cutoff = self.service.sequence
        return (
            self._observe(),
            float(reward),
            False,
            self._ended,
            {
                "schema": OBS_VERSION,
                "action_schema": ACTION_VERSION,
                "before_cutoff_seq": old_cutoff,
                "action_seq": action_seq,
                "observation_cutoff_seq": self.cutoff,
                "metrics_only": after,
                "costs": costs,
                "window": asdict(self.last),
                "control_ledger": [dict(row) for row in self.ledger],
                "pending_right_censored": len(self.service.pending) if self._ended else None,
            },
        )
