from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from monitoring.api import score_window
from shared.monitoring import RouteWindow, RuntimeSignalBatch

END = datetime(2026, 10, 17, 2, 0, tzinfo=UTC)


def w(requests: int, e4: int = 0, e5: int = 0, auth: int = 0) -> RouteWindow:
    return RouteWindow(
        route="GET /payments/{payment_id}",
        requests=requests,
        status_4xx=e4,
        status_5xx=e5,
        auth_failures=auth,
    )


def score(window: RouteWindow, history: list[RouteWindow]):
    return score_window(
        window,
        history,
        window_seconds=60,
        history_seconds=[60] * len(history),
        source="simulated",
        window_end=END,
    )


def test_normal_traffic_is_quiet() -> None:
    hist = [w(100, 2), w(110, 3), w(95, 2), w(105, 2)]
    s = score(w(102, 2), hist)
    assert s.alert_rate == 0 and s.anomaly_score < 0.2 and not s.reasons


def test_enumeration_pattern_raises_rate_and_auth_rules() -> None:
    hist = [w(100, 2), w(110, 3), w(95, 2), w(105, 2)]
    s = score(w(900, 400, 0, 380), hist)
    assert s.alert_rate == 3 and s.anomaly_score == 1.0
    assert any("request rate" in r for r in s.reasons) and any(
        "auth-failure" in r for r in s.reasons
    )


def test_short_history_does_not_invent_a_z_score() -> None:
    s = score(w(900), [w(100)])
    assert (
        s.request_rate_z == 0 and s.history_windows == 1 and "insufficient history" in s.reasons[0]
    )
    s = score(w(10, 0, 5), [])
    assert s.error_ratio == 0.5 and s.alert_rate == 1  # error ratio rule needs no history


def test_batch_validation() -> None:
    with pytest.raises(ValidationError):
        RouteWindow(route="GET /x", requests=5, status_4xx=6)
    with pytest.raises(ValidationError):
        RouteWindow(route="not a route", requests=1)
    with pytest.raises(ValidationError):
        RuntimeSignalBatch(source="simulated", window_start=END, window_end=END, routes=[w(1)])
    with pytest.raises(ValidationError):
        RuntimeSignalBatch(
            source="production",
            window_start=END.replace(minute=0, hour=1),
            window_end=END,
            routes=[w(1)],
        )
