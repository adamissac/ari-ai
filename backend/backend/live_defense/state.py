"""LiveControl lifecycle. Distinct from NIST SP 800-61r3 incident phases.

A recommendation never appears in this machine. The only way into ``executing``
is ``authorized`` → ``executing``.
"""

from __future__ import annotations

from shared.errors import ErrorCode
from shared.live_defense import LiveControlStatus

ALLOWED_TRANSITIONS: dict[LiveControlStatus, frozenset[LiveControlStatus]] = {
    LiveControlStatus.pending_authorization: frozenset(
        {
            LiveControlStatus.authorized,
            LiveControlStatus.rejected,
            LiveControlStatus.escalated,
        }
    ),
    LiveControlStatus.authorized: frozenset(
        {
            LiveControlStatus.executing,
            LiveControlStatus.rejected,
            LiveControlStatus.escalated,
            LiveControlStatus.emergency_stopped,
        }
    ),
    LiveControlStatus.executing: frozenset(
        {
            LiveControlStatus.verifying,
            LiveControlStatus.failed,
            LiveControlStatus.emergency_stopped,
        }
    ),
    LiveControlStatus.verifying: frozenset(
        {
            LiveControlStatus.verified,
            LiveControlStatus.failed,
            LiveControlStatus.emergency_stopped,
        }
    ),
    LiveControlStatus.verified: frozenset(
        {
            LiveControlStatus.expired,
            LiveControlStatus.rolled_back,
            LiveControlStatus.emergency_stopped,
        }
    ),
    LiveControlStatus.failed: frozenset(
        {
            LiveControlStatus.rolled_back,
            LiveControlStatus.escalated,
            LiveControlStatus.emergency_stopped,
        }
    ),
    LiveControlStatus.expired: frozenset(),
    LiveControlStatus.rolled_back: frozenset({LiveControlStatus.escalated}),
    LiveControlStatus.escalated: frozenset(),
    LiveControlStatus.rejected: frozenset(),
    LiveControlStatus.emergency_stopped: frozenset(),
}

TERMINAL = frozenset(status for status, nxt in ALLOWED_TRANSITIONS.items() if not nxt)

# Recommendation-like labels that must never be treated as a control status.
FORBIDDEN_SOURCE_STATUSES = frozenset(
    {
        "recommended",
        "detected",
        "triaged",
        "contained",
        "recovered",
        "closed",
        "NOT_EXECUTED",
        "accept",
    }
)


class IllegalControlTransition(ValueError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"illegal live-control transition {current} -> {target}")
        self.code = ErrorCode.CONFLICT_STATE
        self.current = current
        self.target = target


def can_transition(current: LiveControlStatus, target: LiveControlStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def transition(current: LiveControlStatus, target: LiveControlStatus) -> LiveControlStatus:
    if current.value in FORBIDDEN_SOURCE_STATUSES or str(current) in FORBIDDEN_SOURCE_STATUSES:
        raise IllegalControlTransition(str(current), target.value)
    if not can_transition(current, target):
        raise IllegalControlTransition(current.value, target.value)
    if current is LiveControlStatus.pending_authorization and target is LiveControlStatus.executing:
        raise IllegalControlTransition(current.value, target.value)
    return target
