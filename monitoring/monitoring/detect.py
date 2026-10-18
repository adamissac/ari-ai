"""Deterministic detection rules over authenticated security telemetry. Pure: no I/O.

Each rule looks at one application's recent events and returns detections keyed by a
correlation key ``(category, source)``. The same key while an incident is open folds into
that incident instead of opening another. Thresholds are explicit and recorded in the
rationale so a reader can see exactly why an incident exists.

These are heuristics over events the application reported. A detection means "this
pattern was observed in the telemetry", not "an attacker was confirmed".
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True)
class Event:
    id: str
    kind: str
    occurred_at: datetime
    source_ip: str | None
    route: str | None
    status: int | None
    severity: str | None
    controlled_test: bool


@dataclass(frozen=True)
class Thresholds:
    window: timedelta = timedelta(minutes=5)
    auth_failures: int = 5
    distinct_not_found: int = 8
    server_errors: int = 10


@dataclass(frozen=True)
class Detection:
    category: str
    rule_id: str
    source: str | None
    severity: str
    rationale: str
    event_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def correlation_key(self) -> str:
        return f"{self.category}|{self.source or '*'}"


def _recent(events: Sequence[Event], now: datetime, window: timedelta) -> list[Event]:
    return [e for e in events if now - window <= e.occurred_at <= now + timedelta(seconds=30)]


def detect(events: Sequence[Event], now: datetime, t: Thresholds | None = None) -> list[Detection]:
    t = t or Thresholds()
    recent = _recent(events, now, t.window)
    minutes = int(t.window.total_seconds() // 60)
    out: list[Detection] = []

    by_source: dict[str, list[Event]] = defaultdict(list)
    for e in recent:
        if e.source_ip:
            by_source[e.source_ip].append(e)

    for source, evs in sorted(by_source.items()):
        fails = [e for e in evs if e.kind == "auth_failure"]
        if len(fails) >= t.auth_failures:
            routes = sorted({e.route for e in fails if e.route})
            out.append(
                Detection(
                    category="credential_attack",
                    rule_id="R1_repeated_auth_failures",
                    source=source,
                    severity="high" if len(fails) >= 2 * t.auth_failures else "medium",
                    rationale=(
                        f"{len(fails)} failed sign-ins from {source} within {minutes} min "
                        f"(threshold {t.auth_failures}) on {', '.join(routes) or 'unknown route'}"
                    ),
                    event_ids=tuple(e.id for e in fails),
                )
            )
        missing = [e for e in evs if e.kind == "not_found"]
        distinct = {e.route for e in missing if e.route}
        if len(distinct) >= t.distinct_not_found:
            out.append(
                Detection(
                    category="scanning",
                    rule_id="R2_route_scanning",
                    source=source,
                    severity="medium",
                    rationale=(
                        f"{len(distinct)} distinct missing routes requested by {source} within "
                        f"{minutes} min (threshold {t.distinct_not_found})"
                    ),
                    event_ids=tuple(e.id for e in missing),
                )
            )
        waf = [e for e in evs if e.kind == "waf_alert" and (e.severity in ("high", "critical"))]
        if waf:
            worst = max((e.severity or "high" for e in waf), key=lambda s: SEVERITY_ORDER[s])
            out.append(
                Detection(
                    category="waf_alert",
                    rule_id="R3_high_severity_waf_alert",
                    source=source,
                    severity=worst,
                    rationale=f"{len(waf)} {worst}-severity WAF alert(s) for {source}",
                    event_ids=tuple(e.id for e in waf),
                )
            )

    errors = [e for e in recent if e.kind == "server_error"]
    if len(errors) >= t.server_errors:
        context = [e for e in recent if e.kind in ("deploy", "config_change")]
        out.append(
            Detection(
                category="error_spike",
                rule_id="R4_server_error_spike",
                source=None,
                severity="high" if context else "medium",
                rationale=(
                    f"{len(errors)} server errors within {minutes} min (threshold {t.server_errors})"
                    + (
                        f"; {len(context)} deploy/config change(s) in the same window"
                        if context
                        else ""
                    )
                ),
                event_ids=tuple(e.id for e in errors + context),
            )
        )
    return out
