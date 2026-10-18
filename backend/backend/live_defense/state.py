"""Live incident lifecycle. Pure.

DETECTED → TRIAGED → RECOMMENDED → AUTHORIZED → EXECUTING → VERIFYING → RESOLVED, with a
human gate (AWAITING_APPROVAL → AUTHORIZED | DENIED) and the honest exits ESCALATED,
FAILED and ROLLED_BACK. Closed incidents never reopen (a new pattern opens a new
incident); the one exception is RESOLVED → ROLLED_BACK, when a person removes a control
that outlived its resolved incident. Any transition not listed here is refused.
"""

from __future__ import annotations

from shared.live_defense import LiveIncidentState as S

TERMINAL = frozenset({S.RESOLVED, S.ESCALATED, S.FAILED, S.DENIED, S.ROLLED_BACK})

_EDGES: dict[S, frozenset[S]] = {
    S.DETECTED: frozenset({S.TRIAGED, S.ESCALATED}),
    S.TRIAGED: frozenset({S.RECOMMENDED, S.ESCALATED}),
    # RESOLVED here: the decision was "no control needed" (e.g. noop/logging only).
    S.RECOMMENDED: frozenset({S.AUTHORIZED, S.AWAITING_APPROVAL, S.ESCALATED, S.RESOLVED}),
    S.AWAITING_APPROVAL: frozenset({S.AUTHORIZED, S.DENIED, S.ESCALATED}),
    S.AUTHORIZED: frozenset({S.EXECUTING, S.ESCALATED, S.RESOLVED}),
    S.EXECUTING: frozenset({S.VERIFYING, S.FAILED, S.ROLLED_BACK}),
    S.VERIFYING: frozenset({S.RESOLVED, S.ESCALATED, S.ROLLED_BACK}),
    # A person may still roll back a control that outlived a resolved incident.
    S.RESOLVED: frozenset({S.ROLLED_BACK}),
}

OPEN = frozenset(set(S) - TERMINAL)


class IllegalTransition(ValueError):
    pass


def can(current: S, target: S) -> bool:
    return target in _EDGES.get(current, frozenset())


def check(current: S, target: S) -> None:
    if not can(current, target):
        raise IllegalTransition(f"{current.value} → {target.value} is not a legal transition")
