"""Assessment state machine (docs/08, ADR-0003).

Pure data + pure transition function: no I/O, no LLM. An LLM may rank
hypotheses but never selects a state, grants a permission or skips a gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ..contracts import ErrorCode


class AssessmentState(StrEnum):
    CREATED = "created"
    SCOPE_CHECK = "scope_check"
    INDEXING = "indexing"
    FUNCTIONAL_REVIEW = "functional_review"
    RECON = "recon"
    VALIDATION = "validation"
    ANALYSIS = "analysis"
    DIAGNOSIS = "diagnosis"
    AWAITING_APPROVAL = "awaiting_approval"
    REMEDIATION = "remediation"
    HARDENING = "hardening"
    REPORTING = "reporting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    BUDGET_EXHAUSTED = "budget_exhausted"


class RemediationState(StrEnum):
    PATCHING = "patching"
    VERIFYING = "verifying"
    ACCEPTED = "accepted"
    UNRESOLVED = "unresolved"


TERMINAL: frozenset[AssessmentState] = frozenset(
    {
        AssessmentState.COMPLETED,
        AssessmentState.CANCELLED,
        AssessmentState.FAILED,
        AssessmentState.BUDGET_EXHAUSTED,
    }
)

# The only legal forward edges. Anything else is CONFLICT_STATE.
HAPPY_PATH: dict[AssessmentState, frozenset[AssessmentState]] = {
    AssessmentState.CREATED: frozenset({AssessmentState.SCOPE_CHECK}),
    AssessmentState.SCOPE_CHECK: frozenset({AssessmentState.INDEXING, AssessmentState.FAILED}),
    AssessmentState.INDEXING: frozenset({AssessmentState.FUNCTIONAL_REVIEW, AssessmentState.FAILED}),
    AssessmentState.FUNCTIONAL_REVIEW: frozenset({AssessmentState.RECON}),
    AssessmentState.RECON: frozenset({AssessmentState.VALIDATION, AssessmentState.REPORTING}),
    AssessmentState.VALIDATION: frozenset({AssessmentState.ANALYSIS, AssessmentState.REPORTING}),
    AssessmentState.ANALYSIS: frozenset({AssessmentState.DIAGNOSIS, AssessmentState.REPORTING}),
    AssessmentState.DIAGNOSIS: frozenset({AssessmentState.AWAITING_APPROVAL, AssessmentState.REPORTING}),
    AssessmentState.AWAITING_APPROVAL: frozenset({AssessmentState.REMEDIATION, AssessmentState.REPORTING}),
    AssessmentState.REMEDIATION: frozenset({AssessmentState.HARDENING, AssessmentState.REPORTING}),
    AssessmentState.HARDENING: frozenset({AssessmentState.REPORTING}),
    AssessmentState.REPORTING: frozenset({AssessmentState.COMPLETED}),
}

# From any active state the orchestrator may cancel, fail or stop on budget.
INTERRUPTS: frozenset[AssessmentState] = frozenset(
    {
        AssessmentState.CANCELLED,
        AssessmentState.FAILED,
        AssessmentState.BUDGET_EXHAUSTED,
    }
)


class IllegalTransition(Exception):
    def __init__(self, src: AssessmentState, dst: AssessmentState) -> None:
        super().__init__(f"{ErrorCode.CONFLICT_STATE.value}: {src.value} -> {dst.value}")
        self.src = src
        self.dst = dst


def can_transition(src: AssessmentState, dst: AssessmentState) -> bool:
    if src in TERMINAL:
        return False
    if dst in INTERRUPTS:
        return True
    return dst in HAPPY_PATH.get(src, frozenset())


def transition(src: AssessmentState, dst: AssessmentState) -> AssessmentState:
    if not can_transition(src, dst):
        raise IllegalTransition(src, dst)
    return dst


REMEDIATION_EDGES: dict[RemediationState, frozenset[RemediationState]] = {
    RemediationState.PATCHING: frozenset({RemediationState.VERIFYING, RemediationState.UNRESOLVED}),
    RemediationState.VERIFYING: frozenset(
        {
            RemediationState.ACCEPTED,
            RemediationState.PATCHING,
            RemediationState.UNRESOLVED,
        }
    ),
}

MAX_PATCH_ATTEMPTS = 2


def next_remediation_state(
    current: RemediationState, *, verdict: str | None, attempt: int, patch_failed: bool = False
) -> RemediationState:
    """Per-finding sub-machine (docs/08). `attempt` is the attempt just executed."""
    if current is RemediationState.PATCHING:
        nxt = RemediationState.UNRESOLVED if patch_failed else RemediationState.VERIFYING
    elif current is RemediationState.VERIFYING:
        if verdict == "accepted":
            nxt = RemediationState.ACCEPTED
        elif attempt < MAX_PATCH_ATTEMPTS:
            nxt = RemediationState.PATCHING
        else:
            nxt = RemediationState.UNRESOLVED
    else:
        raise IllegalTransition(AssessmentState.REMEDIATION, AssessmentState.REMEDIATION)
    if nxt not in REMEDIATION_EDGES[current]:
        raise IllegalTransition(AssessmentState.REMEDIATION, AssessmentState.REMEDIATION)
    return nxt


@dataclass
class StateLog:
    """Write-ahead log of transitions; the backend persists these before side effects."""

    entries: list[tuple[str, str, str]] = field(default_factory=list)  # (src, dst, note)

    def record(self, src: AssessmentState, dst: AssessmentState, note: str = "") -> None:
        self.entries.append((src.value, dst.value, note))

    def states(self) -> list[str]:
        return [e[1] for e in self.entries]
