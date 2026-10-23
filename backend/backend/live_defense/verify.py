"""Prove a control had an actual effect. Adapter HTTP 200 is never sufficient."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from backend.live_defense.adapters import AdapterResult, assert_ssrf_safe, call
from shared.base import utcnow
from shared.live_defense import ISOLATED_FIXTURE_SOURCE, LiveControlKind, LiveControlVerification

FIXTURE_PATH = "/payments/pay_fixture"


@dataclass(frozen=True)
class Probe:
    url: str
    source: str | None = None


def _probe_base(control_url: str) -> str:
    host, port, _path = assert_ssrf_safe(control_url)
    return f"http://{host}:{port}"


def _get(url: str, source: str | None = None) -> int:
    headers = {"X-Ari-Source": source} if source else {}
    with httpx.Client(timeout=2.0, follow_redirects=False, trust_env=False) as client:
        response = client.get(url, headers=headers)
        return int(response.status_code)


def verify_control(
    *,
    kind: LiveControlKind,
    control_url: str,
    secret: str,
    control_id: str,
    target_value: str,
    adapter_apply: AdapterResult,
) -> LiveControlVerification:
    inspect = call(
        control_url,
        secret,
        {"op": "inspect", "control_id": control_id},
    )
    statuses: list[int] = []
    observed = False
    detail = "not verified"
    method = "real_http_probes"
    if kind is LiveControlKind.escalate:
        observed = True
        method = "recorded_escalation"
        detail = "Escalate has no adapter effect; the control is a human ticket."
        return LiveControlVerification(
            observed_effect=True,
            adapter_http_status=adapter_apply.http_status,
            probe_http_statuses=[],
            method=method,
            detail=detail,
            verified_at=utcnow(),
        )
    if kind is LiveControlKind.rate_limit:
        url = _probe_base(control_url) + (
            target_value.split(" ", 1)[1] if " " in target_value else FIXTURE_PATH
        )
        first = _get(url)
        second = _get(url)
        statuses = [first, second]
        observed = first == 200 and second == 429
        detail = (
            f"Probe {url}: {first} then {second}. Need 200 then 429."
            if not observed
            else f"Rate limit observed on {url}: {first} then {second}."
        )
    elif kind is LiveControlKind.block_source:
        url = _probe_base(control_url) + FIXTURE_PATH
        blocked = _get(url, source=target_value)
        allowed = _get(url, source="203.0.113.50")
        statuses = [blocked, allowed]
        observed = blocked == 403 and allowed == 200
        detail = f"Source {target_value} -> {blocked}; other source -> {allowed}."
    elif kind is LiveControlKind.increase_logging:
        method = "hmac_inspect_plus_health"
        health = _get(_probe_base(control_url) + "/health")
        statuses = [health]
        present = bool(inspect.body.get("present"))
        level = inspect.body.get("log_level")
        observed = inspect.ok and present and level == "debug" and health == 200
        detail = f"inspect present={present} log_level={level} health={health}"
    adapter_200 = adapter_apply.http_status == 200
    if adapter_200 and not observed:
        detail = f"Adapter HTTP 200 is not effectiveness. {detail}"
    return LiveControlVerification(
        observed_effect=observed,
        adapter_http_status=adapter_apply.http_status,
        probe_http_statuses=statuses,
        method=method,
        detail=detail[:500],
        verified_at=utcnow(),
    )


def verify_removed(
    *,
    control_url: str,
    secret: str,
    control_id: str,
    kind: LiveControlKind,
    target_value: str,
) -> LiveControlVerification:
    inspect = call(control_url, secret, {"op": "inspect", "control_id": control_id})
    present = bool(inspect.body.get("present"))
    statuses: list[int] = []
    observed = inspect.ok and not present
    detail = f"inspect present={present}"
    if kind is LiveControlKind.rate_limit:
        url = _probe_base(control_url) + (
            target_value.split(" ", 1)[1] if " " in target_value else FIXTURE_PATH
        )
        first = _get(url)
        second = _get(url)
        statuses = [first, second]
        observed = observed and first == 200 and second == 200
        detail = f"{detail}; probes {first},{second} (both should be 200 after remove)"
    elif kind is LiveControlKind.block_source:
        url = _probe_base(control_url) + FIXTURE_PATH
        blocked = _get(url, source=target_value or ISOLATED_FIXTURE_SOURCE)
        statuses = [blocked]
        observed = observed and blocked == 200
        detail = f"{detail}; former source -> {blocked}"
    elif kind is LiveControlKind.escalate:
        observed = True
        detail = "Escalate had no adapter state to remove."
    return LiveControlVerification(
        observed_effect=observed,
        adapter_http_status=inspect.http_status,
        probe_http_statuses=statuses,
        method="real_http_probes_after_remove",
        detail=detail[:500],
        verified_at=utcnow(),
    )
