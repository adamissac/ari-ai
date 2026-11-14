"""Live Defense on production applications.

A production app registers its own https control endpoint. Every control still needs an
owner grant and an owner's click; the gate and adapter refuse internal destinations; and
verification asks the app's endpoint instead of sending test traffic. The app side is
``monitoring.controls.AriControls`` running in a real FastAPI app; only the network hop
(TLS to a public address) is replaced by an in-process client.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from helpers import setup_project

from backend import worker
from backend.live_defense import adapters
from backend.live_defense.adapters import AdapterDenied, parse_production_url
from backend.live_defense.authorize import AuthorizationInput, ChannelView, GrantView, check
from monitoring.controls import AriControls

PUBLIC_IP = "93.184.216.34"
HOST = "ctl.example.com"
URL = f"https://{HOST}/live-defense/control"
ROUTE = "GET /payments/{payment_id}"
KINDS = [
    "live_defense_execute",
    "live_defense_verify",
    "live_defense_rollback",
    "live_defense_expire",
    "live_defense_emergency_stop",
]


def _drain() -> None:
    worker.drain(max_jobs=20, kinds=KINDS)


# --- gate (pure) -----------------------------------------------------------


def _inp(**overrides: object) -> AuthorizationInput:
    base: dict[str, object] = dict(
        session_user_id="usr_alice0001",
        claimed_actor_id=None,
        project_id="prj_1",
        application_id="app_1",
        application_exists=True,
        application_environment="production",
        kind="block_source",
        target_type="source_ip",
        target_value="8.8.8.8",
        duration_s=60,
        max_requests=None,
        grant=GrantView(
            id="cgr_1",
            application_id="app_1",
            allowed_kinds=("rate_limit", "block_source", "increase_logging", "escalate"),
            max_duration_s=300,
            hourly_budget=5,
            revoked_at=None,
            expires_at=None,
        ),
        channel=ChannelView(
            host=HOST,
            port=443,
            path="/live-defense/control",
            revoked_at=None,
            scheme="https",
            verified=True,
        ),
        emergency_stop_active=False,
        unresolved_control=False,
        actions_last_hour=0,
        now=datetime(2026, 11, 13, tzinfo=UTC),
    )
    base.update(overrides)
    return AuthorizationInput(**base)  # type: ignore[arg-type]


def test_gate_allows_one_public_address_on_a_production_https_channel() -> None:
    assert check(_inp()).allowed


@pytest.mark.parametrize(
    "value",
    [
        "10.0.0.5",
        "127.0.0.1",
        "169.254.169.254",
        "198.51.100.66",
        "8.8.8.0/24",
        "::ffff:8.8.8.8",
        " 8.8.8.8",
        "x",
    ],
)
def test_gate_denies_non_public_source_blocks_in_production(value: str) -> None:
    decision = check(_inp(target_value=value))
    assert not decision.allowed
    assert any(
        c.name in {"address_policy", "blast_radius"} and not c.passed for c in decision.checks
    )


@pytest.mark.parametrize(
    "channel",
    [
        ChannelView(host="127.0.0.1", port=18080, path="/live-defense/control", revoked_at=None),
        ChannelView(
            host="10.0.0.5", port=443, path="/live-defense/control", revoked_at=None, scheme="https"
        ),
        ChannelView(
            host="localhost",
            port=443,
            path="/live-defense/control",
            revoked_at=None,
            scheme="https",
        ),
        ChannelView(host=HOST, port=443, path="/other", revoked_at=None, scheme="https"),
    ],
)
def test_gate_denies_wrong_channels_for_production(channel: ChannelView) -> None:
    assert not check(_inp(channel=channel)).allowed


def test_owned_test_app_cannot_use_an_https_channel() -> None:
    decision = check(
        _inp(
            application_environment="owned_test",
            kind="increase_logging",
            target_type="application",
            target_value="app_1",
        )
    )
    assert not decision.allowed


def test_unsafe_kinds_stay_denied_in_production() -> None:
    for kind in ("isolate", "block_principal", "firewall", "deploy"):
        assert not check(_inp(kind=kind)).allowed


# --- adapter ---------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://ctl.example.com/live-defense/control",
        "https://ctl.example.com/other",
        "https://ctl.example.com/live-defense/control?x=1",
        "https://user:pw@ctl.example.com/live-defense/control",
        "https://localhost/live-defense/control",
        "https://10.1.2.3/live-defense/control",
        "https://[::1]/live-defense/control",
        "https://169.254.169.254/live-defense/control",
        "https://svc.internal/live-defense/control",
    ],
)
def test_production_url_refusals(url: str) -> None:
    with pytest.raises(AdapterDenied):
        parse_production_url(url)


def test_hostname_that_resolves_inward_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(adapters, "_resolve", lambda _h, _p: [PUBLIC_IP, "10.0.0.9"])
    with pytest.raises(AdapterDenied, match="non-public"):
        parse_production_url(URL)


def test_call_connects_to_the_checked_address_with_tls_name_pinned(monkeypatch) -> None:
    monkeypatch.setattr(adapters, "_resolve", lambda _h, _p: [PUBLIC_IP])
    seen: dict = {}

    class _Resp:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {"ok": True}

    def fake_send(url, body, headers, timeout_s, sni):  # noqa: ANN001
        seen.update(url=url, headers=headers, sni=sni)
        return _Resp()

    monkeypatch.setattr(adapters, "_send", fake_send)
    result = adapters.call(URL, "s" * 40, {"op": "inspect", "control_id": "lct_1"})
    assert result.ok
    assert seen["url"] == f"https://{PUBLIC_IP}:443/live-defense/control"
    assert seen["sni"] == HOST
    assert seen["headers"]["Host"] == HOST
    with pytest.raises(AdapterDenied):
        adapters.call(
            URL,
            "s" * 40,
            {
                "op": "apply",
                "control_id": "lct_2",
                "kind": "block_source",
                "target_value": "10.0.0.1",
            },
        )


# --- end to end through the API, worker and a real app -----------------------


@pytest.fixture
def prod(client_factory, monkeypatch):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    app_doc = alice.post(
        f"/api/v1/projects/{ids['project']}/applications",
        json={"name": "payments production", "environment": "production"},
    )
    assert app_doc.status_code == 201, app_doc.text
    ids["app"] = app_doc.json()["id"]
    monkeypatch.setattr(adapters, "_resolve", lambda _h, _p: [PUBLIC_IP])
    created = alice.post(f"/api/v1/applications/{ids['app']}/control-channel", json={"url": URL})
    assert created.status_code == 201, created.text
    assert created.json()["scheme"] == "https" and created.json()["host"] == HOST

    customer = FastAPI()

    @customer.get("/payments/{payment_id}")
    def payment(payment_id: str) -> dict:
        return {"id": payment_id}

    middleware = AriControls(
        customer,
        secret=created.json()["hmac_secret"],
        client_ip=lambda scope: dict(scope["headers"]).get(b"x-test-ip", b"").decode(),
    )
    app_client = TestClient(middleware)
    sent: list[str] = []

    def to_customer(url, body, headers, timeout_s, sni):  # noqa: ANN001
        assert url.startswith(f"https://{PUBLIC_IP}:443/") and sni == HOST
        sent.append(url)
        return app_client.post("/live-defense/control", content=body, headers=headers)

    monkeypatch.setattr(adapters, "_send", to_customer)
    unverified = _authorize(
        alice, ids, "increase_logging", {"type": "application", "value": ids["app"]}
    )
    assert unverified.status_code == 403 and "ownership challenge" in unverified.text
    proved = alice.post(f"/api/v1/applications/{ids['app']}/control-channel/verify")
    assert proved.status_code == 200, proved.text
    assert proved.json()["verified_at"]
    sent.clear()  # the ownership challenge itself is the only call so far
    grant = alice.post(
        f"/api/v1/projects/{ids['project']}/control-grants",
        json={
            "application_id": ids["app"],
            "allowed_kinds": ["rate_limit", "block_source", "increase_logging", "escalate"],
            "max_duration_s": 300,
            "hourly_budget": 10,
        },
    )
    assert grant.status_code == 201, grant.text
    return {"alice": alice, "bob": bob, "ids": ids, "app": app_client, "sent": sent}


def _authorize(alice, ids, kind, target, max_requests=None):  # noqa: ANN001
    body = {"kind": kind, "target": target, "duration_s": 120, "rationale": "prod control"}
    if max_requests is not None:
        body["max_requests"] = max_requests
    return alice.post(f"/api/v1/applications/{ids['app']}/control-authorizations", json=body)


def test_production_rate_limit_is_applied_verified_and_rolled_back(prod) -> None:
    alice, ids, app = prod["alice"], prod["ids"], prod["app"]
    res = _authorize(alice, ids, "rate_limit", {"type": "route", "value": ROUTE}, max_requests=2)
    assert res.status_code == 201, res.text
    control = res.json()
    assert control["status"] == "authorized"
    assert control["environment_label"] == "PRODUCTION"
    _drain()
    got = alice.get(f"/api/v1/live-controls/{control['id']}").json()
    assert got["status"] == "verified", got
    assert got["verification"]["method"] == "endpoint_inspect"
    assert got["verification"]["probe_http_statuses"] == []
    assert [app.get("/payments/p1").status_code for _ in range(3)] == [200, 200, 429]
    assert app.get("/other").status_code == 404  # other routes untouched

    rb = alice.post(f"/api/v1/live-controls/{control['id']}/rollback", json={"reason": "done"})
    assert rb.status_code == 200, rb.text
    _drain()
    got = alice.get(f"/api/v1/live-controls/{control['id']}").json()
    assert got["status"] == "rolled_back" and got["unresolved"] is False
    assert app.get("/payments/p1").status_code == 200


def test_production_source_block_hits_only_that_address(prod) -> None:
    alice, ids, app = prod["alice"], prod["ids"], prod["app"]
    res = _authorize(alice, ids, "block_source", {"type": "source_ip", "value": "8.8.8.8"})
    assert res.status_code == 201, res.text
    _drain()
    assert alice.get(f"/api/v1/live-controls/{res.json()['id']}").json()["status"] == "verified"
    assert app.get("/payments/p1", headers={"x-test-ip": "8.8.8.8"}).status_code == 403
    assert app.get("/payments/p1", headers={"x-test-ip": "1.1.1.1"}).status_code == 200
    denied = _authorize(alice, ids, "block_source", {"type": "source_ip", "value": "10.0.0.7"})
    assert denied.status_code == 403


def test_production_requires_owner_and_never_runs_without_a_click(prod) -> None:
    import sqlalchemy as sa

    from backend.db import memberships, transaction

    bob, ids, sent = prod["bob"], prod["ids"], prod["sent"]
    with transaction() as conn:
        conn.execute(
            sa.update(memberships)
            .where(memberships.c.user_id == bob.me["user"]["id"])
            .values(role="member")
        )
    res = _authorize(bob, ids, "increase_logging", {"type": "application", "value": ids["app"]})
    assert res.status_code in (403, 404)
    worker.drain(max_jobs=50)  # every queued job kind, shadow and first responder included
    assert sent == []


def test_emergency_stop_clears_production_controls(prod) -> None:
    alice, ids, app = prod["alice"], prod["ids"], prod["app"]
    res = _authorize(alice, ids, "rate_limit", {"type": "route", "value": ROUTE}, max_requests=1)
    _drain()
    assert alice.get(f"/api/v1/live-controls/{res.json()['id']}").json()["status"] == "verified"
    stop = alice.post(f"/api/v1/projects/{ids['project']}/emergency-stop", json={"note": "stop"})
    assert stop.status_code == 201, stop.text
    _drain()
    assert [app.get("/payments/p1").status_code for _ in range(3)] == [200, 200, 200]


def test_unsigned_calls_to_the_app_endpoint_are_refused(prod) -> None:
    app = prod["app"]
    r = app.post("/live-defense/control", json={"op": "emergency_clear", "control_id": "x"})
    assert r.status_code == 401


def test_channel_shape_must_match_environment(client_factory, monkeypatch) -> None:
    monkeypatch.setattr(adapters, "_resolve", lambda _h, _p: ["10.0.0.4"])
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)

    def app(env: str) -> str:
        return alice.post(
            f"/api/v1/projects/{ids['project']}/applications",
            json={"name": env, "environment": env},
        ).json()["id"]

    prod_id, test_id = app("production"), app("owned_test")
    chan = "/api/v1/applications/{}/control-channel"
    assert alice.post(chan.format(prod_id), json={"port": 18080}).status_code == 422
    inward = alice.post(chan.format(prod_id), json={"url": URL})
    assert inward.status_code == 422 and "non-public" in inward.text
    assert alice.post(chan.format(test_id), json={"url": URL}).status_code == 422
    gated = alice.post(
        f"/api/v1/projects/{ids['project']}/applications",
        json={"name": "gated", "environment": "production", "rl_gated_pilot": True},
    ).json()["id"]
    monkeypatch.setattr(adapters, "_resolve", lambda _h, _p: [PUBLIC_IP])
    assert alice.post(chan.format(gated), json={"url": URL}).status_code == 403


def test_endpoint_without_the_secret_cannot_prove_ownership(client_factory, monkeypatch) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    app_id = alice.post(
        f"/api/v1/projects/{ids['project']}/applications",
        json={"name": "p", "environment": "production"},
    ).json()["id"]
    monkeypatch.setattr(adapters, "_resolve", lambda _h, _p: [PUBLIC_IP])
    assert (
        alice.post(f"/api/v1/applications/{app_id}/control-channel", json={"url": URL}).status_code
        == 201
    )
    impostor = TestClient(AriControls(FastAPI(), secret="x" * 43))  # a different secret
    monkeypatch.setattr(
        adapters,
        "_send",
        lambda url, body, headers, t, sni: impostor.post(
            "/live-defense/control", content=body, headers=headers
        ),
    )
    res = alice.post(f"/api/v1/applications/{app_id}/control-channel/verify")
    assert res.status_code == 422
    view = alice.get(f"/api/v1/applications/{app_id}/control-channel").json()
    assert view["verified_at"] is None


def test_gate_refuses_an_unverified_production_channel() -> None:
    channel = ChannelView(
        host=HOST, port=443, path="/live-defense/control", revoked_at=None, scheme="https"
    )
    decision = check(_inp(channel=channel))
    assert not decision.allowed
    assert "ownership challenge" in decision.reason


def test_owner_protected_addresses_are_never_blocked() -> None:
    grant = _inp().grant
    from dataclasses import replace

    protected = replace(grant, protected_sources=("8.8.8.0/24", "1.1.1.1/32"))
    for value in ("8.8.8.8", "1.1.1.1"):
        decision = check(_inp(grant=protected, target_value=value))
        assert not decision.allowed and "protected" in decision.reason, value
    assert check(_inp(grant=protected, target_value="9.9.9.9")).allowed


def test_grant_rejects_a_malformed_protected_entry(prod) -> None:
    alice, ids = prod["alice"], prod["ids"]
    bad = alice.post(
        f"/api/v1/projects/{ids['project']}/control-grants",
        json={
            "application_id": ids["app"],
            "allowed_kinds": ["block_source"],
            "protected_sources": ["office"],
        },
    )
    assert bad.status_code == 422


def test_channel_secret_is_encrypted_at_rest_when_a_key_is_set(prod, monkeypatch) -> None:
    import sqlalchemy as sa
    from cryptography.fernet import Fernet

    from backend.db import control_channels, transaction
    from backend.live_defense.sealing import seal, unseal
    from backend.settings import get_settings

    monkeypatch.setenv("CONTROL_SECRET_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    try:
        sealed = seal("hkt_ctl_example_secret_value")
        assert sealed.startswith("fernet:v1:") and "example" not in sealed
        assert unseal(sealed) == "hkt_ctl_example_secret_value"
        assert unseal("hkt_ctl_legacy_plaintext") == "hkt_ctl_legacy_plaintext"
        alice = prod["alice"]
        app_id = alice.post(
            f"/api/v1/projects/{prod['ids']['project']}/applications",
            json={"name": "sealed", "environment": "production"},
        ).json()["id"]
        made = alice.post(f"/api/v1/applications/{app_id}/control-channel", json={"url": URL})
        assert made.status_code == 201, made.text
        with transaction() as conn:
            stored = conn.execute(
                sa.select(control_channels.c.hmac_secret).where(
                    control_channels.c.application_id == app_id
                )
            ).scalar_one()
        assert stored.startswith("fernet:v1:")
        assert made.json()["hmac_secret"] not in stored
        assert unseal(stored) == made.json()["hmac_secret"]
    finally:
        monkeypatch.delenv("CONTROL_SECRET_KEY")
        get_settings.cache_clear()


NODE_APP = (
    "require('http').createServer((q, r) => r.end('ok ' + q.url))"
    ".listen(Number(process.argv[1]), '127.0.0.1')"
)


def _free() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_port(port: int) -> None:
    import socket
    import time

    deadline = time.time() + 15
    while time.time() < deadline:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError(f"port {port} never opened")


@pytest.mark.skipif(__import__("shutil").which("node") is None, reason="needs node")
def test_ari_controls_a_node_app_through_the_sidecar_proxy(client_factory, monkeypatch) -> None:
    """API + worker -> monitoring.proxy (separate process) -> a Node HTTP server."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    import httpx

    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    app_id = alice.post(
        f"/api/v1/projects/{ids['project']}/applications",
        json={"name": "node shop", "environment": "production"},
    ).json()["id"]
    monkeypatch.setattr(adapters, "_resolve", lambda _h, _p: [PUBLIC_IP])
    secret = alice.post(f"/api/v1/applications/{app_id}/control-channel", json={"url": URL}).json()[
        "hmac_secret"
    ]
    node_port, proxy_port = _free(), _free()
    node = subprocess.Popen(["node", "-e", NODE_APP, str(node_port)])
    proxy = subprocess.Popen(
        [sys.executable, "-m", "monitoring.proxy", "--listen", f"127.0.0.1:{proxy_port}"],
        env={
            **os.environ,
            "ARI_UPSTREAM": f"http://127.0.0.1:{node_port}",
            "ARI_CONTROL_SECRET": secret,
        },
        cwd=Path(__file__).resolve().parents[2] / "monitoring",
    )
    try:
        _wait_port(node_port)
        _wait_port(proxy_port)
        base = f"http://127.0.0.1:{proxy_port}"

        def to_proxy(url, body, headers, timeout_s, sni):  # noqa: ANN001
            assert sni == HOST
            return httpx.post(f"{base}/live-defense/control", content=body, headers=headers)

        monkeypatch.setattr(adapters, "_send", to_proxy)
        assert (
            alice.post(f"/api/v1/applications/{app_id}/control-channel/verify").status_code == 200
        )
        assert (
            alice.post(
                f"/api/v1/projects/{ids['project']}/control-grants",
                json={
                    "application_id": app_id,
                    "allowed_kinds": ["rate_limit"],
                    "max_duration_s": 300,
                },
            ).status_code
            == 201
        )
        res = alice.post(
            f"/api/v1/applications/{app_id}/control-authorizations",
            json={
                "kind": "rate_limit",
                "target": {"type": "route", "value": "GET /cart/{id}"},
                "duration_s": 120,
                "max_requests": 1,
            },
        )
        assert res.status_code == 201, res.text
        _drain()
        control = alice.get(f"/api/v1/live-controls/{res.json()['id']}").json()
        assert control["status"] == "verified", control
        assert httpx.get(f"{base}/cart/1").text == "ok /cart/1"
        assert httpx.get(f"{base}/cart/2").status_code == 429
        alice.post(f"/api/v1/live-controls/{control['id']}/rollback", json={"reason": "done"})
        _drain()
        assert alice.get(f"/api/v1/live-controls/{control['id']}").json()["status"] == "rolled_back"
        assert httpx.get(f"{base}/cart/3").status_code == 200
    finally:
        proxy.terminate()
        node.terminate()
        proxy.wait(10)
        node.wait(10)
