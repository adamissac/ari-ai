"""scope_guard branch coverage (SEC-002). Pure function, exhaustive cases."""

from __future__ import annotations

from datetime import timedelta

import pytest

from security_agents.contracts import AgentName, ScopeStatus
from security_agents.scope_guard import ActionRequest, check

from .conftest import NOW, TARGET_ID, make_scope

RUN = ActionRequest(action="run_check", target_id=TARGET_ID, check_category="access_control.ownership", agent=AgentName.PROBE)


def test_active_scope_allows_probe_check():
    d = check(make_scope(), RUN, NOW)
    assert d.allowed and d.reason_code == "OK" and d.scope_id == "scp_test"


def test_missing_scope_denied():
    d = check(None, RUN, NOW)
    assert not d.allowed and d.reason_code == "MISSING_SCOPE" and d.scope_id is None


@pytest.mark.parametrize(
    "status", [ScopeStatus.PENDING, ScopeStatus.EXPIRED, ScopeStatus.REVOKED]
)
def test_non_active_status_denied(status):
    d = check(make_scope(status=status), RUN, NOW)
    assert not d.allowed and d.reason_code == "SCOPE_NOT_ACTIVE"


def test_expired_by_clock_denied():
    d = check(make_scope(expires_at=NOW - timedelta(seconds=1)), RUN, NOW)
    assert not d.allowed and d.reason_code == "SCOPE_EXPIRED"


def test_expiry_boundary_is_exclusive():
    assert not check(make_scope(expires_at=NOW), RUN, NOW).allowed
    assert check(make_scope(expires_at=NOW + timedelta(seconds=1)), RUN, NOW).allowed


def test_naive_now_denied():
    d = check(make_scope(), RUN, NOW.replace(tzinfo=None))
    assert not d.allowed and d.reason_code == "SCOPE_EXPIRED"


def test_unapproved_scope_denied():
    d = check(make_scope(approved_by=None), RUN, NOW)
    assert not d.allowed and d.reason_code == "SCOPE_NOT_APPROVED"


def test_self_approval_denied_in_multi_member_org():
    scope = make_scope(approved_by="usr_same", requested_by="usr_same")
    assert not check(scope, RUN, NOW, org_member_count=2).allowed
    # A single-member org may self-approve (docs/15 §3).
    assert check(scope, RUN, NOW, org_member_count=1).allowed


def test_target_not_in_scope_denied():
    d = check(make_scope(), ActionRequest(action="run_check", target_id="tgt_other",
                                          check_category="access_control.ownership",
                                          agent=AgentName.PROBE), NOW)
    assert not d.allowed and d.reason_code == "TARGET_NOT_IN_SCOPE"


def test_missing_target_denied():
    d = check(make_scope(), ActionRequest(action="run_check", check_category="access_control.ownership",
                                          agent=AgentName.PROBE), NOW)
    assert not d.allowed and d.reason_code == "TARGET_NOT_IN_SCOPE"


def test_category_not_allowed_denied():
    d = check(make_scope(categories=["input_validation.bounds"]), RUN, NOW)
    assert not d.allowed and d.reason_code == "CATEGORY_NOT_ALLOWED"


def test_category_required_for_run_check():
    d = check(make_scope(), ActionRequest(action="run_check", target_id=TARGET_ID, agent=AgentName.PROBE), NOW)
    assert not d.allowed and d.reason_code == "CATEGORY_REQUIRED"


@pytest.mark.parametrize(
    "agent", [AgentName.SCOUT, AgentName.TRACE, AgentName.DIAGNOSE, AgentName.PATCH, AgentName.FORTIFY]
)
def test_only_probe_and_verify_may_touch_a_target(agent):
    d = check(make_scope(), ActionRequest(action="run_check", target_id=TARGET_ID,
                                          check_category="access_control.ownership", agent=agent), NOW)
    assert not d.allowed and d.reason_code == "AGENT_NOT_PERMITTED"


def test_verify_may_recheck():
    d = check(make_scope(), ActionRequest(action="run_check", target_id=TARGET_ID,
                                          check_category="access_control.ownership",
                                          agent=AgentName.VERIFY), NOW)
    assert d.allowed


def test_assessment_start_needs_no_target():
    assert check(make_scope(), ActionRequest(action="assessment_start"), NOW).allowed


def test_attach_network_requires_in_scope_target():
    allowed = check(make_scope(), ActionRequest(action="attach_network", target_id=TARGET_ID,
                                                agent=AgentName.PROBE), NOW)
    denied = check(make_scope(), ActionRequest(action="attach_network", target_id="tgt_x",
                                               agent=AgentName.PROBE), NOW)
    assert allowed.allowed and not denied.allowed


def test_build_target_allowed_without_category():
    d = check(make_scope(), ActionRequest(action="build_target", target_id=TARGET_ID, agent=AgentName.PROBE), NOW)
    assert d.allowed


def test_decision_is_pure():
    scope = make_scope()
    first = check(scope, RUN, NOW)
    second = check(scope, RUN, NOW)
    assert first.model_dump() == second.model_dump()
