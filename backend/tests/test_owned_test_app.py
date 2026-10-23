"""Owned-test fixture: allowlist, idempotency, logging restore, probe header."""

from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient

from backend.live_defense.owned_test_app import ControlPlane, create_app
from shared.live_defense import (
    FIXTURE_SOURCE_HEADER,
    ISOLATED_FIXTURE_SOURCE,
    OWNED_TEST_OTHER_PROBE_SOURCE,
)


def _apply(
    plane: ControlPlane,
    control_id: str,
    *,
    kind: str = "increase_logging",
    target_type: str = "application",
    target_value: str = "app",
    max_requests: int | None = None,
    expires_at: float | None = None,
    log_level: str = "debug",
) -> tuple[int, dict[str, object]]:
    return plane.apply(
        {
            "op": "apply",
            "control_id": control_id,
            "kind": kind,
            "target_type": target_type,
            "target_value": target_value,
            "max_requests": max_requests,
            "log_level": log_level,
            "expires_at_unix": expires_at if expires_at is not None else time.time() + 60,
        }
    )


def test_block_source_rejects_non_fixture_ips() -> None:
    plane = ControlPlane("secret")
    status, body = _apply(
        plane,
        "lct_bad_ip",
        kind="block_source",
        target_type="source_ip",
        target_value="8.8.8.8",
    )
    assert status == 400
    assert body["ok"] is False
    status, _ = _apply(
        plane,
        "lct_ok_ip",
        kind="block_source",
        target_type="source_ip",
        target_value=ISOLATED_FIXTURE_SOURCE,
    )
    assert status == 200
    blocked = plane.enforce("GET", "/payments/pay_fixture", ISOLATED_FIXTURE_SOURCE)
    assert blocked is not None and blocked.status_code == 403
    other = plane.enforce("GET", "/payments/pay_fixture", OWNED_TEST_OTHER_PROBE_SOURCE)
    assert other is None


def test_stale_retry_with_mutated_binding_is_conflict() -> None:
    plane = ControlPlane("secret")
    expires = time.time() + 90
    status, first = _apply(
        plane,
        "lct_stale",
        kind="rate_limit",
        target_type="route",
        target_value="GET /payments/pay_fixture",
        max_requests=1,
        expires_at=expires,
    )
    assert status == 200 and first.get("idempotent") is False
    status, conflict = _apply(
        plane,
        "lct_stale",
        kind="rate_limit",
        target_type="route",
        target_value="GET /other",
        max_requests=1,
        expires_at=expires,
    )
    assert status == 409
    assert conflict.get("conflict") is True
    assert plane.controls["lct_stale"].target_value == "GET /payments/pay_fixture"
    status, retry = _apply(
        plane,
        "lct_stale",
        kind="rate_limit",
        target_type="route",
        target_value="GET /payments/pay_fixture",
        max_requests=1,
        expires_at=expires,
    )
    assert status == 200 and retry.get("idempotent") is True


def test_concurrent_same_payload_stays_single_control() -> None:
    plane = ControlPlane("secret")
    expires = time.time() + 60
    results: list[tuple[int, dict[str, object]]] = []

    def worker() -> None:
        results.append(
            _apply(
                plane,
                "lct_concurrent",
                kind="rate_limit",
                target_type="route",
                target_value="GET /payments/pay_fixture",
                max_requests=2,
                expires_at=expires,
            )
        )

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert all(status == 200 for status, _ in results)
    idempotent = [body.get("idempotent") for _, body in results]
    assert idempotent.count(False) == 1
    assert idempotent.count(True) == 7
    assert list(plane.controls) == ["lct_concurrent"]


def test_increase_logging_expiry_rollback_and_kill_switch_restore_prior() -> None:
    plane = ControlPlane("secret")
    assert plane.log_level == "info"
    _apply(plane, "lct_log_a", expires_at=time.time() + 0.4)
    assert plane.log_level == "debug"
    _apply(plane, "lct_log_b", expires_at=time.time() + 30)
    assert plane.log_level == "debug"
    plane.apply({"op": "remove", "control_id": "lct_log_a"})
    assert plane.log_level == "debug"
    assert "lct_log_a" not in plane.controls
    plane.apply({"op": "expire", "control_id": "lct_log_b"})
    assert plane.log_level == "info"
    _apply(plane, "lct_log_c", expires_at=time.time() + 30)
    assert plane.log_level == "debug"
    plane.apply({"op": "emergency_clear", "control_id": "est_all"})
    assert plane.log_level == "info"
    assert plane.controls == {}
    restarted = ControlPlane("secret")
    assert restarted.log_level == "info"
    assert restarted.controls == {}


def test_logging_ttl_without_worker_restores_prior() -> None:
    plane = ControlPlane("secret")
    _apply(plane, "lct_ttl_log", expires_at=time.time() + 0.2)
    assert plane.log_level == "debug"
    time.sleep(0.25)
    plane.enforce("GET", "/health", "127.0.0.1")
    assert plane.log_level == "info"
    assert "lct_ttl_log" not in plane.controls


def test_x_ari_source_is_fixture_probe_header_not_production_identity() -> None:
    app = create_app("secret")
    client = TestClient(app)
    plane: ControlPlane = app.state.plane
    _apply(
        plane,
        "lct_block",
        kind="block_source",
        target_type="source_ip",
        target_value=ISOLATED_FIXTURE_SOURCE,
    )
    blocked = client.get(
        "/payments/pay_fixture",
        headers={FIXTURE_SOURCE_HEADER: ISOLATED_FIXTURE_SOURCE},
    )
    assert blocked.status_code == 403
    allowed = client.get(
        "/payments/pay_fixture",
        headers={FIXTURE_SOURCE_HEADER: OWNED_TEST_OTHER_PROBE_SOURCE},
    )
    assert allowed.status_code == 200
    spoofed_public = client.get("/payments/pay_fixture", headers={FIXTURE_SOURCE_HEADER: "8.8.8.8"})
    assert spoofed_public.status_code == 200
    spoofed_prod = client.get(
        "/payments/pay_fixture",
        headers={FIXTURE_SOURCE_HEADER: "customer-tenant-prod"},
    )
    assert spoofed_prod.status_code == 200
