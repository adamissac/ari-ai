"""Pure research observation adapter, NOT a trainable environment or collector.

No traffic generation, control execution, model calls, randomness or reward shaping.
Versioned proposal only; production/v6 layouts and shared contracts are untouched.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from shared.evidence import EvidenceRef

from rl_defense.research.authorization_provider import AuthorizationSnapshot

OBSERVATION_VERSION: Literal["adaptive-context/0.1"] = "adaptive-context/0.1"
ACTION_VERSION: Literal["adaptive-actions/0.1"] = "adaptive-actions/0.1"
FEATURES = (
    "request_count",
    "auth_failure_count",
    "authorization_denial_count",
    "unauthorized_attempt_count",
    "distinct_resource_count",
    "repeat_attempt_count",
    "request_count_delta",
    "owner_count",
    "delegated_count",
    "unauthorized_count",
    "unknown_context_count",
    "context_age_max",
    "revocation_observed_count",
    "active_control_count",
    "control_remaining_max",
    "cooldown_remaining",
    "intervention_count",
    "intervention_budget_remaining",
    "owner_completed_count",
    "delegated_completed_count",
    "owner_adaptive_denial_count",
    "delegated_adaptive_denial_count",
    "cumulative_disruption",
    "valid_target_count",
    "missing_context_fraction",
    "observation_age",
    "adapter_available",
    "control_available",
    "supported_action_count",
    "elapsed_ticks",
    "remaining_ticks",
    "observed_disruption_count",
)
ACTIONS = (
    "noop",
    "diagnostic_logging",
    "human_investigation",
    "scoped_rate_limit",
    "source_containment",
)
# No measurable residual intervention has been demonstrated. Never widen from a
# caller-supplied boolean, detector label or policy preference.
ACTION_MASK = (True, False, False, False, False)


@dataclass(frozen=True)
class ObservedRead:
    """Trusted completed-read telemetry input; not accepted from HTTP clients.

    Producer must retain response-identity verification and authoritative snapshots.
    availability is knowledge-arrival time, distinct from request occurrence.
    This phase supplies no real collector; unit fixtures exercise the boundary.
    """

    event_id: str
    started_tick: int
    completed_tick: int
    available_tick: int
    snapshot: AuthorizationSnapshot = field(repr=False)
    status: int
    adaptive_denial: bool
    evidence: EvidenceRef

    def __post_init__(self) -> None:
        if not self.event_id or any(
            type(x) is not int
            for x in (self.started_tick, self.completed_tick, self.available_tick, self.status)
        ):
            raise ValueError("event identity and integer times/status required")
        if not 0 <= self.started_tick <= self.completed_tick <= self.available_tick:
            raise ValueError("invalid event/arrival ordering")
        if not 100 <= self.status <= 599 or type(self.adaptive_denial) is not bool:
            raise ValueError("invalid outcome")
        if self.adaptive_denial and self.status < 400:
            raise ValueError("a successful response cannot be a defense denial")
        if self.snapshot.context.observed_at != self.started_tick:
            raise ValueError("authorization capture must bind to the request start")


@dataclass(frozen=True)
class CandidateObservation:
    cutoff: int
    window_start: int
    clock_domain: str
    values: tuple[float | None, ...]
    evidence: tuple[EvidenceRef, ...]
    schema_version: Literal["adaptive-context/0.1"] = OBSERVATION_VERSION
    action_version: Literal["adaptive-actions/0.1"] = ACTION_VERSION
    action_mask: tuple[bool, ...] = ACTION_MASK

    def __post_init__(self) -> None:
        if (
            type(self.cutoff) is not int
            or type(self.window_start) is not int
            or not 0 <= self.window_start <= self.cutoff
            or not self.clock_domain
            or len(self.values) != len(FEATURES)
            or any(
                v is not None and (type(v) not in (float, int) or not math.isfinite(v))
                for v in self.values
            )
            or self.schema_version != OBSERVATION_VERSION
            or self.action_version != ACTION_VERSION
            or self.action_mask != ACTION_MASK
        ):
            raise ValueError("invalid candidate observation/version/capability")

    def encode(self) -> tuple[float, ...]:
        """69 raw channels: 32 values, 32 known bits, five feasibility bits.

        Missing value slots use zero only with their known bit cleared. These are
        unnormalized diagnostic features, not compatible with any saved network.
        """
        return (
            *(0.0 if v is None else v for v in self.values),
            *(float(v is not None) for v in self.values),
            *(float(v) for v in self.action_mask),
        )


def observation(
    events: tuple[ObservedRead, ...], *, window_start: int, cutoff: int, clock_domain: str
) -> CandidateObservation:
    """Available completed prefix only. Never query current permission tables.

    An old snapshot is classified at request start, not at the later cutoff.
    Late arrivals are omitted here and must be reported by future instrumentation;
    they cannot rewrite a previously frozen observation.
    """
    if (
        type(window_start) is not int
        or type(cutoff) is not int
        or not 0 <= window_start <= cutoff
        or not clock_domain
    ):
        raise ValueError("valid trusted clock and cutoff required")
    # Filter first: even malformed/duplicate future records cannot affect a prefix.
    visible = tuple(e for e in events if window_start <= e.available_tick < cutoff)
    if len({e.event_id for e in visible}) != len(visible):
        raise ValueError("duplicate visible event")
    if any(e.snapshot.authority != "payments-lite-owned-research" for e in visible):
        raise ValueError("unexpected research authority")
    if any(e.snapshot.clock_domain != clock_domain for e in visible):
        raise ValueError("incomparable clock domains")
    values: dict[str, float | None] = dict.fromkeys(FEATURES)
    classes = [e.snapshot.classify(tick=e.started_tick) for e in visible]
    for category in ("owner", "delegated", "unauthorized"):
        values[f"{category}_count"] = float(classes.count(category))
    values["unknown_context_count"] = float(classes.count("unknown"))
    values["request_count"] = float(len(visible))
    values["unauthorized_attempt_count"] = values["unauthorized_count"]
    values["missing_context_fraction"] = (
        classes.count("unknown") / len(visible) if visible else None
    )
    # Distinct resources only among known authorization contexts; unknown coverage
    # stays explicit. This is NOT a count of all resources in the application.
    values["distinct_resource_count"] = float(
        len(
            {
                e.snapshot.context.resource
                for e, c in zip(visible, classes, strict=True)
                if c != "unknown"
            }
        )
    )
    values["observation_age"] = (
        float(cutoff - max(e.completed_tick for e in visible)) if visible else None
    )
    values["context_age_max"] = (
        float(max(cutoff - e.started_tick for e in visible)) if visible else None
    )
    pairs = tuple(zip(visible, classes, strict=True))
    release_classes = {e.event_id: e.snapshot.classify(tick=e.completed_tick) for e in visible}
    for category in ("owner", "delegated"):
        eligible = [(e, c) for e, c in pairs if c == category]
        # A grant that expired (or snapshot that went stale) before response/denial
        # release cannot certify valid access at that point. Preserve uncertainty.
        complete = all(release_classes[e.event_id] == category for e, _ in eligible)
        values[f"{category}_completed_count"] = (
            float(sum(e.status == 200 for e, _ in eligible)) if complete else None
        )
        values[f"{category}_adaptive_denial_count"] = (
            float(sum(e.adaptive_denial for e, _ in eligible)) if complete else None
        )
    costs = [values[f"{c}_adaptive_denial_count"] for c in ("owner", "delegated")]
    values["observed_disruption_count"] = (
        sum(v for v in costs if v is not None) if all(v is not None for v in costs) else None
    )
    values["supported_action_count"] = float(sum(ACTION_MASK))
    return CandidateObservation(
        cutoff,
        window_start,
        clock_domain,
        tuple(values[f] for f in FEATURES),
        tuple(e.evidence for e in sorted(visible, key=lambda e: e.event_id)),
    )


def validate_action(action: int) -> None:
    """Independent hard rejection; never silently substitute a noop."""
    if type(action) is not int or not 0 <= action < len(ACTION_MASK) or not ACTION_MASK[action]:
        raise ValueError("unsupported research action; only noop is currently feasible")


def measured_channels(obs: CandidateObservation) -> dict[str, float | None]:
    """Descriptive known authorized denials only; no inferred adaptive benefit.

    Unknown-context denials cannot be counted as known legitimate or hostile.
    No dollar, latency, duration or counterfactual reward is invented.
    """
    values = dict(zip(FEATURES, obs.values, strict=True))
    return {
        "adaptive_security_reward": None,
        "owner_denial_cost": values["owner_adaptive_denial_count"],
        "delegated_denial_cost": values["delegated_adaptive_denial_count"],
        "operational_cost": None,
        "unnecessary_duration_cost": None,
    }
