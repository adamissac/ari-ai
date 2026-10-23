"""Live Defense Phase 5: shadow-pilot readiness without executable enforcement."""

from __future__ import annotations

from datetime import timedelta

from helpers import setup_project

from shared.base import utcnow
from shared.live_defense import PILOT_UNSUPPORTED_CLAIMS


def _batch(end, requests: int = 12, e4: int = 0, auth: int = 0) -> dict:
    return {
        "source": "owned_staging",
        "window_start": (end - timedelta(minutes=1)).isoformat(),
        "window_end": end.isoformat(),
        "routes": [
            {
                "route": "GET /payments/{payment_id}",
                "requests": requests,
                "status_4xx": e4,
                "auth_failures": auth,
            }
        ],
    }


def test_rotate_revoke_disconnect_and_restart_ingest(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    pid = ids["project"]
    app = alice.post(
        f"/api/v1/projects/{pid}/applications",
        json={"name": "payments staging", "environment": "owned_test"},
    ).json()
    assert app["shadow_mode"] is True
    minted = alice.post(f"/api/v1/applications/{app['id']}/ingest-tokens")
    assert minted.status_code == 201
    old = minted.json()["token"]
    now = utcnow()
    ack = alice.post(
        f"/api/v1/ingest/runtime/{pid}",
        json=_batch(now),
        headers={"Authorization": f"Bearer {old}"},
    )
    assert ack.status_code == 202, ack.text

    rotated = alice.post(f"/api/v1/applications/{app['id']}/ingest-tokens/rotate")
    assert rotated.status_code == 201, rotated.text
    body = rotated.json()
    new = body["token"]
    assert new.startswith("hkt_ing_")
    assert new != old
    assert old not in rotated.text or body["revoked_ids"]
    listed = alice.get(f"/api/v1/projects/{pid}/ingest-tokens").json()["items"]
    assert new not in alice.get(f"/api/v1/projects/{pid}/ingest-tokens").text
    assert any(item["id"] in body["revoked_ids"] for item in listed)

    stale = alice.post(
        f"/api/v1/ingest/runtime/{pid}",
        json=_batch(now + timedelta(minutes=2)),
        headers={"Authorization": f"Bearer {old}"},
    )
    assert stale.status_code == 401
    restarted = alice.post(
        f"/api/v1/ingest/runtime/{pid}",
        json=_batch(now + timedelta(minutes=2)),
        headers={"Authorization": f"Bearer {new}"},
    )
    assert restarted.status_code == 202, restarted.text

    verified = alice.post(f"/api/v1/applications/{app['id']}/shadow-verify")
    assert verified.status_code == 200
    assert verified.json()["verification"] == "ingest_seen"
    assert verified.json()["shadow_mode"] is True

    stopped = alice.post(f"/api/v1/applications/{app['id']}/disconnect")
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["verification"] == "disconnected"
    assert stopped.json()["disconnected_at"] is not None
    disabled = alice.post(
        f"/api/v1/ingest/runtime/{pid}",
        json=_batch(now + timedelta(minutes=3)),
        headers={"Authorization": f"Bearer {new}"},
    )
    assert disabled.status_code == 401
    assert alice.post(f"/api/v1/applications/{app['id']}/ingest-tokens").status_code == 409
    assert alice.post(f"/api/v1/applications/{app['id']}/ingest-tokens/rotate").status_code == 409


def test_pilot_report_is_honest_and_health_stays_unknown(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    outsider = client_factory("mallory")
    outsider.post("/api/v1/projects", json={"name": "other-org"})
    pid = ids["project"]
    alice.post(
        f"/api/v1/projects/{pid}/applications",
        json={"name": "payments staging", "environment": "sandbox"},
    )
    health = alice.get(f"/api/v1/projects/{pid}/defense-health").json()
    assert health["status"] == "unknown"
    assert health["worker_status"] == "unknown"
    assert health["telemetry_status"] == "unknown"
    assert health["policy_status"] == "unknown"
    report = alice.get(f"/api/v1/projects/{pid}/pilot-report")
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["shadow_mode"] is True
    assert body["health"]["status"] == "unknown"
    assert "shadow prevented breaches" in body["unsupported_claims"]
    for claim in PILOT_UNSUPPORTED_CLAIMS:
        assert claim in body["unsupported_claims"]
    assert any("HTTP 200" in item for item in body["caveats"])
    assert body["health"]["status"] != "healthy"
    assert outsider.get(f"/api/v1/projects/{pid}/pilot-report").status_code == 404


def test_phase5_has_no_browser_callable_enforcement_routes() -> None:
    from backend.main import app

    post_paths = [p.lower() for p, ops in app.openapi()["paths"].items() if "post" in ops]
    for path in post_paths:
        for token in ("/isolate", "/block-source", "/block_source", "/rate-limit", "/apply"):
            assert token not in path, path
    assert any("ingest-tokens/rotate" in p for p in post_paths)
    assert any(p.endswith("/disconnect") or "/disconnect" in p for p in post_paths)
