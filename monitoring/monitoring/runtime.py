"""Explainable runtime anomaly scoring (docs/10 "Runtime anomaly signals"). Pure.

Each route window is compared only with that route's own recent windows:

* request-rate z-score (needs >= MIN_HISTORY windows; otherwise reported as 0 with a reason);
* change in (4xx + 5xx) / requests versus the historical mean;
* change in auth failures (401/403) / requests versus the historical mean.

``alert_rate`` counts triggered rules; ``anomaly_score`` in [0, 1] is the strongest
normalized rule. These are heuristics over aggregated counters, not attack detection:
a high score means "worth investigating", never "confirmed compromise".
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime

from shared.monitoring import RouteScore, RouteWindow, RuntimeSource

MIN_HISTORY = 3
Z_ALERT = 3.0
ERROR_DELTA_ALERT = 0.20
AUTH_DELTA_ALERT = 0.10
ANOMALY_EVENT_THRESHOLD = 0.5


def _ratio(n: int, d: int) -> float:
    return n / d if d > 0 else 0.0


def score_window(
    window: RouteWindow,
    history: Sequence[RouteWindow],
    *,
    window_seconds: float,
    history_seconds: Sequence[float],
    source: RuntimeSource,
    window_end: datetime,
) -> RouteScore:
    if len(history) != len(history_seconds):
        raise ValueError("history and history_seconds must align")
    rate = window.requests / window_seconds
    err = _ratio(window.status_4xx + window.status_5xx, window.requests)
    auth = _ratio(window.auth_failures, window.requests)
    reasons: list[str] = []
    hist_err = (
        sum(_ratio(h.status_4xx + h.status_5xx, h.requests) for h in history) / len(history)
        if history
        else 0.0
    )
    hist_auth = (
        sum(_ratio(h.auth_failures, h.requests) for h in history) / len(history) if history else 0.0
    )
    z = 0.0
    if len(history) >= MIN_HISTORY:
        rates = [h.requests / s for h, s in zip(history, history_seconds, strict=True)]
        mean = sum(rates) / len(rates)
        std = math.sqrt(sum((r - mean) ** 2 for r in rates) / len(rates))
        z = (rate - mean) / max(std, 0.1 * mean, 1e-6)
    else:
        reasons.append(
            f"insufficient history ({len(history)}/{MIN_HISTORY} windows): rate z not computed"
        )
    err_delta = err - hist_err
    auth_delta = auth - hist_auth
    triggered = 0
    if z >= Z_ALERT:
        triggered += 1
        reasons.append(f"request rate z={z:.1f} >= {Z_ALERT}")
    if err_delta >= ERROR_DELTA_ALERT:
        triggered += 1
        reasons.append(f"error ratio {err:.2f} up {err_delta:+.2f} vs history")
    if auth_delta >= AUTH_DELTA_ALERT:
        triggered += 1
        reasons.append(f"auth-failure ratio {auth:.2f} up {auth_delta:+.2f} vs history")
    anomaly = max(
        0.0,
        min(
            1.0,
            max(
                z / (2 * Z_ALERT),
                err_delta / (2 * ERROR_DELTA_ALERT),
                auth_delta / (2 * AUTH_DELTA_ALERT),
            ),
        ),
    )
    return RouteScore(
        route=window.route,
        source=source,
        window_end=window_end,
        request_rate_z=round(z, 4),
        error_ratio=round(err, 6),
        error_ratio_delta=round(err_delta, 6),
        auth_failure_ratio=round(auth, 6),
        auth_failure_ratio_delta=round(auth_delta, 6),
        history_windows=len(history),
        alert_rate=float(triggered),
        anomaly_score=round(anomaly, 4),
        reasons=reasons,
    )
