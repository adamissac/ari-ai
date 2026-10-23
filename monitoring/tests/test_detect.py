"""Deterministic Live Defense rules: real counters only; HTTP 200 is not IDOR."""

from __future__ import annotations

from monitoring.detect import detect, is_quiet, view_from_window
from shared.live_defense import AuthorizationContext
from shared.monitoring import PrincipalCounts, RouteWindow


def _view(
    route: str = "GET /payments/{payment_id}",
    requests: int = 20,
    e4: int = 0,
    e5: int = 0,
    auth: int = 0,
    principals: list[PrincipalCounts] | None = None,
    anomaly: float = 0.0,
):
    window = RouteWindow(
        route=route,
        requests=requests,
        status_4xx=e4,
        status_5xx=e5,
        auth_failures=auth,
        principals=principals or [],
    )
    return view_from_window(window, source="owned_staging", anomaly_score=anomaly)


def test_benign_window_is_quiet_and_has_no_attack_finding() -> None:
    views = [_view(requests=20, e4=1, auth=0)]
    hits = detect(views)
    assert [h.rule_id for h in hits] == ["http_200_ownership_unknown"]
    assert hits[0].suggested_action == "noop"
    assert hits[0].authorization_context is AuthorizationContext.unverified
    assert "not IDOR" in hits[0].reason
    assert is_quiet(views, hits) is True


def test_repeated_auth_failures() -> None:
    views = [_view(requests=20, e4=12, auth=12, anomaly=0.7)]
    hits = detect(views)
    ids = [h.rule_id for h in hits]
    assert "repeated_auth_failures" in ids
    assert "error_spike" in ids
    assert is_quiet(views, hits) is False


def test_cross_tenant_requires_reporter_classification() -> None:
    views = [
        _view(
            requests=10,
            principals=[
                PrincipalCounts(principal="prn_alice01", cross_tenant=4, own=6),
            ],
        )
    ]
    hits = detect(views)
    assert [h.rule_id for h in hits] == ["cross_tenant_with_ownership"]
    assert hits[0].suggested_action == "block_principal"
    assert hits[0].authorization_context is AuthorizationContext.verified
    assert "HTTP 200" in hits[0].reason or "Not inferred" in hits[0].reason


def test_http_200_without_principals_is_not_idor() -> None:
    views = [_view(requests=15, e4=0, e5=0)]
    hits = detect(views)
    assert all(h.rule_id != "cross_tenant_with_ownership" for h in hits)
    assert all("IDOR" not in h.rule_id for h in hits)
    unknown = [h for h in hits if h.rule_id == "http_200_ownership_unknown"]
    assert len(unknown) == 1
    assert unknown[0].suggested_action == "noop"


def test_scanning_pattern_needs_several_noisy_routes() -> None:
    views = [_view(route=f"GET /missing/{i}", requests=10, e4=10) for i in range(4)]
    hits = detect(views)
    assert any(h.rule_id == "scanning_pattern" for h in hits)


def test_one_route_without_ownership_context_keeps_the_batch_unverified() -> None:
    from monitoring.detect import authorization_context

    classified = _view(
        route="GET /a/{id}",
        requests=10,
        principals=[PrincipalCounts(principal="prn_alice01", cross_tenant=0, own=10)],
    )
    unclassified = _view(route="GET /b/{id}", requests=10)
    assert authorization_context([classified]) is AuthorizationContext.verified
    assert authorization_context([classified, unclassified]) is AuthorizationContext.unverified
