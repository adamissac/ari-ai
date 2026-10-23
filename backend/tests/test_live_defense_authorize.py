"""Pure authorization gate: 15 checks, fail closed, no model authority."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.live_defense.authorize import AuthorizationInput, ChannelView, GrantView, check
from backend.live_defense.state import ALLOWED_TRANSITIONS, IllegalControlTransition, transition
from shared.live_defense import AUTHORIZATION_CHECKS, ISOLATED_FIXTURE_SOURCE, LiveControlStatus

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
USER = "usr_01JFIXTURE0000000000000USR"
APP = "app_01JFIXTURE0000000000000APP"
PRJ = "prj_01JFIXTURE0000000000000PRJ"


def _grant() -> GrantView:
    return GrantView(
        id="cgr_01JFIXTURE0000000000000CGR",
        application_id=APP,
        allowed_kinds=("rate_limit", "block_source", "increase_logging", "escalate"),
        max_duration_s=300,
        hourly_budget=5,
        revoked_at=None,
        expires_at=None,
    )


def _channel() -> ChannelView:
    return ChannelView(host="127.0.0.1", port=18080, path="/live-defense/control", revoked_at=None)


def _inp(**overrides: object) -> AuthorizationInput:
    base = dict(
        session_user_id=USER,
        claimed_actor_id=None,
        project_id=PRJ,
        application_id=APP,
        application_exists=True,
        application_environment="owned_test",
        kind="rate_limit",
        target_type="route",
        target_value="GET /payments/pay_fixture",
        duration_s=60,
        max_requests=2,
        grant=_grant(),
        channel=_channel(),
        emergency_stop_active=False,
        unresolved_control=False,
        actions_last_hour=0,
        now=NOW,
    )
    base.update(overrides)
    return AuthorizationInput(**base)  # type: ignore[arg-type]


def test_all_fifteen_checks_run_and_happy_path_allows() -> None:
    decision = check(_inp())
    assert [c.name for c in decision.checks] == list(AUTHORIZATION_CHECKS)
    assert len(decision.checks) == 15
    assert decision.allowed
    assert all(c.passed for c in decision.checks)


def test_typed_usr_in_claimed_actor_is_not_identity() -> None:
    decision = check(_inp(claimed_actor_id=USER))
    assert not decision.allowed
    assert any(c.name == "authenticated_session" and not c.passed for c in decision.checks)


def test_missing_session_fails_closed() -> None:
    decision = check(_inp(session_user_id=None))
    assert not decision.allowed


def test_isolate_and_principal_block_are_not_allowlisted() -> None:
    for kind in ("isolate", "block_principal", "credential_rotation"):
        decision = check(
            _inp(kind=kind, target_type="source_ip", target_value=ISOLATED_FIXTURE_SOURCE)
        )
        assert not decision.allowed
        assert decision.abstain


def test_cidr_and_loopback_and_link_local_denied() -> None:
    for value in ("198.51.100.0/24", "127.0.0.1", "::1", "169.254.1.1", "10.0.0.5", "0.0.0.0"):
        decision = check(
            _inp(
                kind="block_source",
                target_type="source_ip",
                target_value=value,
                max_requests=None,
            )
        )
        assert not decision.allowed, value


def test_isolated_fixture_source_is_allowed() -> None:
    decision = check(
        _inp(
            kind="block_source",
            target_type="source_ip",
            target_value=ISOLATED_FIXTURE_SOURCE,
            max_requests=None,
        )
    )
    assert decision.allowed


def test_rules_originated_still_requires_grant() -> None:
    decision = check(_inp(grant=None))
    assert not decision.allowed
    assert any(c.name == "owner_grant_exact_kind" and not c.passed for c in decision.checks)


def test_kill_switch_and_unresolved_fail_closed() -> None:
    assert not check(_inp(emergency_stop_active=True)).allowed
    assert not check(_inp(unresolved_control=True)).allowed


def test_channel_must_be_loopback_fixed_path() -> None:
    decision = check(
        _inp(
            channel=ChannelView(
                host="example.com", port=18080, path="/live-defense/control", revoked_at=None
            )
        )
    )
    assert not decision.allowed
    decision = check(
        _inp(
            channel=ChannelView(
                host="127.0.0.1", port=80, path="/live-defense/control", revoked_at=None
            )
        )
    )
    assert not decision.allowed


def test_recommendation_cannot_transition_to_executing() -> None:
    assert (
        LiveControlStatus.executing
        not in ALLOWED_TRANSITIONS[LiveControlStatus.pending_authorization]
    )
    try:
        transition(LiveControlStatus.pending_authorization, LiveControlStatus.executing)
        raise AssertionError("pending_authorization must not jump to executing")
    except IllegalControlTransition:
        pass
    assert (
        transition(LiveControlStatus.authorized, LiveControlStatus.executing)
        is LiveControlStatus.executing
    )
