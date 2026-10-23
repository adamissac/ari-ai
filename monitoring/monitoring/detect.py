"""Deterministic Live Defense detection rules. Pure: no I/O, no LLM.

Findings come only from counters the reporter sent. HTTP 200 is never treated as
IDOR. Cross-tenant claims require the reporter's ownership classification
(``principals``). Missing ownership context is recorded as unverified, not as an
authorization finding.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from shared.live_defense import AuthorizationContext
from shared.monitoring import PrincipalCounts, RouteWindow, RuntimeSource
from shared.rl import DefenseActionName

AUTH_FAILURE_RATIO = 0.25
AUTH_FAILURE_MIN = 5
ERROR_RATIO = 0.50
ERROR_MIN_REQUESTS = 8
SCAN_ROUTE_RATIO = 0.50
SCAN_MIN_ROUTES = 4


@dataclass(frozen=True)
class WindowView:
    """One scored ingest route window, already validated by the ingest schema."""

    route: str
    requests: int
    status_4xx: int
    status_5xx: int
    auth_failures: int
    principals: tuple[PrincipalCounts, ...]
    anomaly_score: float
    source: RuntimeSource
    successes: int


@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    reason: str
    suggested_action: DefenseActionName
    authorization_context: AuthorizationContext
    route: str | None = None


def view_from_window(
    window: RouteWindow, *, source: RuntimeSource, anomaly_score: float
) -> WindowView:
    successes = max(0, window.requests - window.status_4xx - window.status_5xx)
    return WindowView(
        route=window.route,
        requests=window.requests,
        status_4xx=window.status_4xx,
        status_5xx=window.status_5xx,
        auth_failures=window.auth_failures,
        principals=tuple(window.principals),
        anomaly_score=anomaly_score,
        source=source,
        successes=successes,
    )


def authorization_context(windows: Sequence[WindowView]) -> AuthorizationContext:
    succeeded = [w for w in windows if w.successes > 0]
    if succeeded:  # one route without ownership context keeps the whole batch unverified
        if all(w.principals for w in succeeded):
            return AuthorizationContext.verified
        return AuthorizationContext.unverified
    if any(w.principals for w in windows):
        return AuthorizationContext.verified
    return AuthorizationContext.missing


def detect(windows: Sequence[WindowView]) -> list[RuleHit]:
    """Return rule hits for this batch. Never invents an IDOR from HTTP 200."""
    hits: list[RuleHit] = []
    ctx = authorization_context(windows)
    for window in windows:
        hits.extend(_route_hits(window, ctx))
    scan = _scanning(windows, ctx)
    if scan is not None:
        hits.append(scan)
    return hits


def _route_hits(window: WindowView, ctx: AuthorizationContext) -> list[RuleHit]:
    hits: list[RuleHit] = []
    if window.requests >= AUTH_FAILURE_MIN:
        ratio = window.auth_failures / window.requests
        if ratio >= AUTH_FAILURE_RATIO and window.auth_failures >= AUTH_FAILURE_MIN:
            hits.append(
                RuleHit(
                    rule_id="repeated_auth_failures",
                    reason=(
                        f"{window.route}: {window.auth_failures}/{window.requests} "
                        f"auth failures (ratio {ratio:.2f})"
                    ),
                    suggested_action="raise_monitoring",
                    authorization_context=ctx,
                    route=window.route,
                )
            )
    errors = window.status_4xx + window.status_5xx
    if window.requests >= ERROR_MIN_REQUESTS:
        ratio = errors / window.requests
        if ratio >= ERROR_RATIO:
            hits.append(
                RuleHit(
                    rule_id="error_spike",
                    reason=(
                        f"{window.route}: {errors}/{window.requests} errors "
                        f"(ratio {ratio:.2f}); not classified as an exploit"
                    ),
                    suggested_action="raise_monitoring",
                    authorization_context=ctx,
                    route=window.route,
                )
            )
    flagged = [p for p in window.principals if p.cross_tenant > 0]
    if flagged:
        refs = ", ".join(p.principal for p in flagged)
        hits.append(
            RuleHit(
                rule_id="cross_tenant_with_ownership",
                reason=(
                    f"{window.route}: reporter classified cross-tenant reads for {refs}. "
                    "Not inferred from HTTP 200."
                ),
                suggested_action="block_principal",
                authorization_context=AuthorizationContext.verified,
                route=window.route,
            )
        )
    elif window.successes > 0 and not window.principals:
        hits.append(
            RuleHit(
                rule_id="http_200_ownership_unknown",
                reason=(
                    f"{window.route}: {window.successes} successful responses without "
                    "ownership context. HTTP 200 is not IDOR."
                ),
                suggested_action="noop",
                authorization_context=AuthorizationContext.unverified,
                route=window.route,
            )
        )
    return hits


def _scanning(windows: Sequence[WindowView], ctx: AuthorizationContext) -> RuleHit | None:
    noisy = [
        w.route
        for w in windows
        if w.requests > 0 and (w.status_4xx / w.requests) >= SCAN_ROUTE_RATIO
    ]
    if len(set(noisy)) < SCAN_MIN_ROUTES:
        return None
    return RuleHit(
        rule_id="scanning_pattern",
        reason=(
            f"{len(set(noisy))} distinct routes with high 4xx ratios in one window "
            f"({', '.join(sorted(set(noisy))[:8])})"
        ),
        suggested_action="escalate_to_human",
        authorization_context=ctx,
    )


def is_quiet(windows: Sequence[WindowView], hits: Sequence[RuleHit]) -> bool:
    """A quiet window has no flagged principals and no high-severity rule hits."""
    if any(p.cross_tenant > 0 for w in windows for p in w.principals):
        return False
    if any(
        h.rule_id in {"repeated_auth_failures", "error_spike", "scanning_pattern"} for h in hits
    ):
        return False
    if any(w.anomaly_score >= 0.5 for w in windows):
        return False
    return True
