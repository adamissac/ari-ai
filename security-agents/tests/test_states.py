"""Assessment state machine: legal transitions, interrupts, remediation sub-flow (SEC-012)."""

from __future__ import annotations

import pytest

from security_agents.workflow import (
    MAX_PATCH_ATTEMPTS,
    IllegalTransition,
    StateLog,
    can_transition,
    next_remediation_state,
    transition,
)
from security_agents.workflow import (
    AssessmentState as S,
)
from security_agents.workflow import (
    RemediationState as R,
)
from security_agents.workflow.states import HAPPY_PATH, TERMINAL

HAPPY_SEQUENCE = [
    S.CREATED, S.SCOPE_CHECK, S.INDEXING, S.FUNCTIONAL_REVIEW, S.RECON, S.VALIDATION,
    S.ANALYSIS, S.DIAGNOSIS, S.AWAITING_APPROVAL, S.REMEDIATION, S.HARDENING, S.REPORTING,
    S.COMPLETED,
]


def test_full_happy_path_is_legal():
    state = S.CREATED
    for nxt in HAPPY_SEQUENCE[1:]:
        state = transition(state, nxt)
    assert state is S.COMPLETED


def test_every_non_terminal_state_has_a_forward_edge():
    for state in S:
        if state in TERMINAL:
            continue
        assert HAPPY_PATH.get(state), f"{state.value} is a dead end"


@pytest.mark.parametrize("state", sorted(TERMINAL, key=lambda s: s.value))
def test_terminal_states_accept_nothing(state):
    for target in S:
        assert not can_transition(state, target), f"{state.value} -> {target.value}"


@pytest.mark.parametrize(
    "src,dst",
    [
        (S.CREATED, S.RECON),
        (S.SCOPE_CHECK, S.VALIDATION),
        (S.RECON, S.DIAGNOSIS),
        (S.VALIDATION, S.REMEDIATION),
        (S.DIAGNOSIS, S.REMEDIATION),       # approval gate cannot be skipped
        (S.AWAITING_APPROVAL, S.HARDENING),
        (S.REPORTING, S.RECON),
        (S.COMPLETED, S.REPORTING),
    ],
)
def test_illegal_transitions_raise(src, dst):
    assert not can_transition(src, dst)
    with pytest.raises(IllegalTransition):
        transition(src, dst)


@pytest.mark.boundary
def test_remediation_cannot_be_entered_without_the_approval_state():
    """SB-07-adjacent: the approval gate is a state, so it cannot be bypassed."""
    assert not can_transition(S.DIAGNOSIS, S.REMEDIATION)
    assert can_transition(S.DIAGNOSIS, S.AWAITING_APPROVAL)
    assert can_transition(S.AWAITING_APPROVAL, S.REMEDIATION)


@pytest.mark.parametrize("interrupt", [S.CANCELLED, S.FAILED, S.BUDGET_EXHAUSTED])
@pytest.mark.parametrize(
    "active",
    [S.SCOPE_CHECK, S.RECON, S.VALIDATION, S.ANALYSIS, S.REMEDIATION, S.HARDENING, S.REPORTING],
)
def test_any_active_state_can_be_interrupted(active, interrupt):
    assert transition(active, interrupt) is interrupt


def test_early_exit_to_reporting_is_legal_from_each_stage():
    for state in (S.RECON, S.VALIDATION, S.ANALYSIS, S.DIAGNOSIS, S.AWAITING_APPROVAL, S.REMEDIATION):
        assert can_transition(state, S.REPORTING)


def test_scope_check_can_only_proceed_or_fail():
    assert HAPPY_PATH[S.SCOPE_CHECK] == frozenset({S.INDEXING, S.FAILED})


# --------------------------------------------------------------------------- remediation


def test_patch_then_verify_accepted():
    state = next_remediation_state(R.PATCHING, verdict=None, attempt=1)
    assert state is R.VERIFYING
    assert next_remediation_state(state, verdict="accepted", attempt=1) is R.ACCEPTED


def test_rejected_first_attempt_retries_patch():
    assert next_remediation_state(R.VERIFYING, verdict="rejected", attempt=1) is R.PATCHING


def test_rejected_second_attempt_is_unresolved():
    assert next_remediation_state(R.VERIFYING, verdict="rejected", attempt=2) is R.UNRESOLVED
    assert MAX_PATCH_ATTEMPTS == 2


def test_patch_failure_is_unresolved_without_verification():
    assert next_remediation_state(R.PATCHING, verdict=None, attempt=1, patch_failed=True) is R.UNRESOLVED


def test_no_verdict_is_treated_as_rejection():
    assert next_remediation_state(R.VERIFYING, verdict=None, attempt=2) is R.UNRESOLVED


@pytest.mark.parametrize("terminal", [R.ACCEPTED, R.UNRESOLVED])
def test_remediation_terminal_states_do_not_continue(terminal):
    with pytest.raises(IllegalTransition):
        next_remediation_state(terminal, verdict="accepted", attempt=1)


def test_remediation_loop_is_bounded():
    """Two patch attempts at most, whatever the verdicts are."""
    attempts = 0
    state = R.PATCHING
    while state in (R.PATCHING, R.VERIFYING):
        if state is R.PATCHING:
            attempts += 1
            state = next_remediation_state(state, verdict=None, attempt=attempts)
        else:
            state = next_remediation_state(state, verdict="rejected", attempt=attempts)
    assert state is R.UNRESOLVED
    assert attempts == MAX_PATCH_ATTEMPTS


# --------------------------------------------------------------------------- log


def test_state_log_records_order():
    log = StateLog()
    log.record(S.CREATED, S.SCOPE_CHECK, "gate")
    log.record(S.SCOPE_CHECK, S.INDEXING)
    assert log.states() == ["scope_check", "indexing"]
    assert log.entries[0] == ("created", "scope_check", "gate")
