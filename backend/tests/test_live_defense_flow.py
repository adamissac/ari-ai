"""Live defense end to end on real PostgreSQL, a real Ari API over HTTP and the real owned
test application (examples/live-defense-target) over HTTP.

Controlled test traffic (RFC 5737 addresses, ``X-Ari-Test-Traffic: 1``) hits the owned app;
the app reports telemetry with its ingest token; the worker detects, decides, authorizes,
applies a signed control on the app, verifies it with new telemetry, notifies, expires and
rolls back. No model is configured, so every decision here must be labelled as the
deterministic fallback; one test injects a labelled TEST runner that recommends noop.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import sqlalchemy as sa
import uvicorn
from cryptography.fernet import Fernet

from backend.db import defense_actions, live_apps, transaction
from backend.live_defense import engine, policy
from backend.worker import drain
from shared.base import utcnow

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "examples" / "live-defense-target"))
import target_app  # noqa: E402

ATTACKER = "203.0.113.7"
TEST = {"X-Ari-Test-Traffic": "1", "X-Forwarded-For": ATTACKER}
PIPELINE = ["live_defense_process", "live_defense_respond", "live_defense_execute"]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class _Server(uvicorn.Server):
    def install_signal_handlers(self) -> None:  # running in a thread
        pass


def _serve(app: Any) -> tuple[str, _Server]:
    port = _free_port()
    server = _Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    return f"http://127.0.0.1:{port}", server


@pytest.fixture
def stack(
    client_factory, settings_override, monkeypatch: pytest.MonkeyPatch
) -> Iterator[dict[str, Any]]:
    from backend.main import create_app

    monkeypatch.setenv("TARGET_NO_FLUSHER", "1")
    target_port = _free_port()
    settings_override(
        live_defense_secret_key=Fernet.generate_key().decode(),
        live_defense_allowed_private_hosts=f"127.0.0.1:{target_port}",
        live_defense_verify_interval_s="0",
        live_defense_verify_attempts="2",
    )
    api_url, api_server = _serve(create_app())
    alice = client_factory("alice")
    p = alice.post("/api/v1/projects", json={"name": "lumen-shop"})
    assert p.status_code == 201, p.text
    pid = p.json()["id"]
    tok = alice.post(f"/api/v1/projects/{pid}/ingest-tokens").json()
    base = f"http://127.0.0.1:{target_port}"
    created = alice.post(
        f"/api/v1/projects/{pid}/live/apps",
        json={
            "name": "Lumen Shop",
            "environment": "owned_test",
            "control_url": f"{base}/ari",
            "notify_url": f"{base}/ari/notifications",
            "auto_response": True,
            "protected_sources": ["198.51.100.1"],
        },
    )
    assert created.status_code == 201, created.text
    app_id, secret = created.json()["app"]["id"], created.json()["signing_secret"]
    cfg = target_app.Config(
        app_id=app_id,
        ingest_url=f"{api_url}/api/v1/ingest/live/{app_id}",
        ingest_token=tok["token"],
        signing_secret=secret,
    )
    target = target_app.create_app(cfg)
    server = _Server(
        uvicorn.Config(target, host="127.0.0.1", port=target_port, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    yield {
        "alice": alice,
        "project": pid,
        "app_id": app_id,
        "secret": secret,
        "target": target,
        "target_url": base,
        "client": client_factory,
    }
    server.should_exit = True
    api_server.should_exit = True


def grant(alice, app_id: str, kind: str = "block_source", max_duration_s: int = 900) -> None:
    r = alice.post(
        f"/api/v1/live/apps/{app_id}/grants",
        json={"kind": kind, "max_duration_s": max_duration_s, "hourly_budget": 5},
    )
    assert r.status_code == 201, r.text


def attack(s: dict[str, Any], n: int = 6) -> list[int]:
    codes = [
        httpx.post(
            f"{s['target_url']}/login",
            json={"username": "demo@lumen.test", "password": f"guess{i}"},
            headers=TEST,
        ).status_code
        for i in range(n)
    ]
    s["target"].state.flush_once()
    return codes


def incident(s: dict[str, Any]) -> dict[str, Any]:
    items = s["alice"].get(f"/api/v1/projects/{s['project']}/live/incidents").json()["items"]
    assert len(items) == 1, items
    return s["alice"].get(f"/api/v1/live/incidents/{items[0]['id']}").json()


def test_detect_block_verify_notify_expire(stack) -> None:
    s = stack
    grant(s["alice"], s["app_id"])
    assert attack(s) == [401] * 6
    drain(kinds=PIPELINE)
    d = incident(s)
    inc, act = d["incident"], d["actions"][0]
    assert inc["state"] == "VERIFYING" and inc["controlled_test"] and inc["event_count"] == 6
    dec = inc["decision"]
    assert dec["rl"]["status"] == "unavailable" and dec["final"]["selected_by"] == "rules"
    assert dec["final"]["kind"] == "block_source" and dec["final"]["target"] == ATTACKER
    assert dec["authorization"]["outcome"] == "authorized"
    assert act["status"] == "active" and act["mode"] == "automatic" and act["target"] == ATTACKER
    controls = httpx.get(f"{s['target_url']}/ari/state").json()["controls"]
    assert [(c["kind"], c["target"], c["active"]) for c in controls] == [
        ("block_source", ATTACKER, True)
    ]

    # New evidence: the attacker keeps trying and the application now refuses it.
    assert attack(s, 2) == [403, 403]
    ok = httpx.post(
        f"{s['target_url']}/login",
        json={"username": "demo@lumen.test", "password": "correct horse battery staple"},
        headers={"X-Forwarded-For": "198.51.100.20"},
    )
    assert ok.status_code == 200
    drain()
    d = incident(s)
    act = d["actions"][0]
    assert d["incident"]["state"] == "RESOLVED"
    assert act["status"] == "verified" and act["verification"]["result"] == "effective"
    assert act["verification"]["blocked_after"] == 2 and act["verification"]["attempts_after"] == 0
    states = [t["to_state"] for t in d["timeline"] if t["event"] == "state_changed"]
    assert states == [
        "DETECTED",
        "TRIAGED",
        "RECOMMENDED",
        "AUTHORIZED",
        "EXECUTING",
        "VERIFYING",
        "RESOLVED",
    ]
    assert {e["kind"] for e in d["events"]} == {"auth_failure", "blocked"}
    delivered = {n["event"] for n in d["notifications"] if n["status"] == "delivered"}
    assert {"incident.detected", "control.active", "incident.resolved"} <= delivered
    received = httpx.get(f"{s['target_url']}/ari/state").json()["notifications"]
    assert any(n["event"] == "incident.resolved" for n in received)

    # A stalled expiry is re-driven by reconciliation and the control comes off the app.
    with transaction() as conn:
        conn.execute(sa.update(defense_actions).values(expires_at=utcnow() - timedelta(minutes=1)))
    assert engine.reconcile()["expire"] == 1
    drain()
    d = incident(s)
    assert d["actions"][0]["status"] == "expired"
    assert not httpx.get(f"{s['target_url']}/ari/state").json()["controls"][0]["active"]
    assert any(t["event"] == "control_expired" for t in d["timeline"])

    status = s["alice"].get(f"/api/v1/projects/{s['project']}/live/status").json()
    assert (
        status["counts"]["resolved_incidents"] == 1
        and status["counts"]["automatic_actions_executed"] == 1
    )
    assert status["monitoring"] == "offline"  # no worker heartbeat in tests: said plainly
    assert status["rl"]["loadable"] is False and "RL_CHECKPOINT_PATH" in status["rl"]["reason"]


def test_rl_noop_is_recorded_separately_from_the_rule_block(
    stack, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_live_defense_units import Runner

    monkeypatch.setattr(policy, "RUNNER_OVERRIDE", Runner("noop"))
    s = stack
    grant(s["alice"], s["app_id"])
    attack(s)
    drain(kinds=PIPELINE)
    dec = incident(s)["incident"]["decision"]
    assert (
        dec["rl"]["status"] == "ok"
        and dec["rl"]["action"] == "noop"
        and dec["rl"]["policy_version"] == "TEST-RUNNER"
    )
    assert dec["rl"]["mapped_kind"] is None
    assert dec["rules"]["minimum_kind"] == "block_source"
    assert dec["final"]["selected_by"] == "rules" and dec["final"]["kind"] == "block_source"


def test_human_approval_deny_rollback_and_permissions(stack) -> None:
    s = stack
    alice = s["alice"]
    attack(s)  # no grant: the gate routes the block to a person
    drain(kinds=PIPELINE)
    d = incident(s)
    act = d["actions"][0]
    assert d["incident"]["state"] == "AWAITING_APPROVAL" and act["status"] == "pending_approval"
    assert d["incident"]["decision"]["authorization"]["reason_code"] == "NO_GRANT"

    outsider = s["client"]("mallory")
    assert outsider.post(f"/api/v1/live/actions/{act['id']}/approve", json={}).status_code == 404
    no_csrf = s["client"]()
    no_csrf.cookies = alice.cookies
    assert no_csrf.post(f"/api/v1/live/actions/{act['id']}/approve", json={}).status_code == 403

    key = {"Idempotency-Key": "approve-1"}
    first = alice.post(
        f"/api/v1/live/actions/{act['id']}/approve", json={"reason": "confirmed"}, headers=key
    )
    again = alice.post(
        f"/api/v1/live/actions/{act['id']}/approve", json={"reason": "confirmed"}, headers=key
    )
    assert first.status_code == again.status_code == 200 and first.json() == again.json()
    assert first.json()["status"] == "authorized" and first.json()["mode"] == "human_approved"
    late = alice.post(f"/api/v1/live/actions/{act['id']}/deny", json={})
    assert late.status_code == 409 and late.json()["error"]["code"] == "CONFLICT_STATE"

    drain(kinds=PIPELINE)
    assert incident(s)["actions"][0]["status"] == "active"
    r = alice.post(f"/api/v1/live/actions/{act['id']}/rollback", json={"reason": "false positive"})
    assert r.status_code == 200 and r.json()["status"] == "rollback_requested"
    drain(kinds=["live_defense_rollback"])
    d = incident(s)
    assert d["actions"][0]["status"] == "rolled_back" and d["incident"]["state"] == "ROLLED_BACK"
    assert not httpx.get(f"{s['target_url']}/ari/state").json()["controls"][0]["active"]
    twice = alice.post(f"/api/v1/live/actions/{act['id']}/rollback", json={})
    assert twice.status_code == 409


def test_deny_closes_the_incident_without_executing(stack) -> None:
    s = stack
    attack(s)
    drain(kinds=PIPELINE)
    act = incident(s)["actions"][0]
    r = s["alice"].post(f"/api/v1/live/actions/{act['id']}/deny", json={"reason": "known tester"})
    assert r.status_code == 200 and r.json()["status"] == "denied"
    drain()
    d = incident(s)
    assert (
        d["incident"]["state"] == "DENIED"
        and httpx.get(f"{s['target_url']}/ari/state").json()["controls"] == []
    )


def test_ingest_auth_dedupe_and_secret_never_returned(stack) -> None:
    s = stack
    url = f"/api/v1/ingest/live/{s['app_id']}"
    ev = {
        "event_id": "e-1",
        "kind": "auth_failure",
        "occurred_at": utcnow().isoformat(),
        "source_ip": ATTACKER,
    }
    anon = s["client"]()
    assert anon.post(url, json={"events": [ev]}).status_code == 401
    assert (
        anon.post(url, json={"events": [ev]}, headers={"Authorization": "Bearer nope"}).status_code
        == 401
    )
    other = s["alice"].post("/api/v1/projects", json={"name": "other"}).json()["id"]
    other_tok = s["alice"].post(f"/api/v1/projects/{other}/ingest-tokens").json()["token"]
    assert (
        anon.post(
            url, json={"events": [ev]}, headers={"Authorization": f"Bearer {other_tok}"}
        ).status_code
        == 401
    )
    bad = {**ev, "source_ip": "not-an-ip"}
    tok = s["target"].state.cfg.ingest_token
    assert (
        anon.post(
            url, json={"events": [bad]}, headers={"Authorization": f"Bearer {tok}"}
        ).status_code
        == 422
    )
    first = anon.post(url, json={"events": [ev]}, headers={"Authorization": f"Bearer {tok}"}).json()
    second = anon.post(
        url, json={"events": [ev]}, headers={"Authorization": f"Bearer {tok}"}
    ).json()
    assert (first["accepted"], second["accepted"], second["duplicates"]) == (1, 0, 1)

    listing = s["alice"].get(f"/api/v1/projects/{s['project']}/live/apps").text
    status = s["alice"].get(f"/api/v1/projects/{s['project']}/live/status").text
    assert (
        s["secret"] not in listing
        and s["secret"] not in status
        and '"secret_storage":"encrypted"' in listing
    )
    with transaction() as conn:
        stored = conn.execute(sa.select(live_apps.c.secret_ciphertext)).scalar_one()
    assert s["secret"] not in stored


def test_unsafe_control_urls_are_refused_at_registration(stack) -> None:
    s = stack
    for url in ("http://169.254.169.254/latest", "http://127.0.0.1:1/ari", "file:///etc/passwd"):
        r = s["alice"].post(
            f"/api/v1/projects/{s['project']}/live/apps",
            json={"name": "x", "environment": "production", "control_url": url},
        )
        assert r.status_code == 422, (url, r.text)
        assert r.json()["error"]["details"]["field"] == "control_url"
