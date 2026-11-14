"""The sidecar proxy in front of a non-Python app (Node), over real loopback HTTP."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="needs node for the upstream app"
)

SECRET = "hkt_ctl_" + "s" * 43
NODE_APP = r"""
const http = require('http');
http.createServer((req, res) => {
  let body = '';
  req.on('data', c => body += c);
  req.on('end', () => {
    res.setHeader('content-type', 'application/json');
    res.setHeader('x-upstream', 'node');
    if (req.url.startsWith('/teapot')) { res.statusCode = 418; }
    res.end(JSON.stringify({method: req.method, url: req.url, body,
      xff: req.headers['x-forwarded-for'] || null, auth: req.headers['authorization'] || null}));
  });
}).listen(Number(process.argv[1]), '127.0.0.1');
"""


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait(port: int) -> None:
    deadline = time.time() + 15
    while time.time() < deadline:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError(f"port {port} never opened")


@pytest.fixture(scope="module")
def stack() -> Iterator[dict]:
    node_port, proxy_port = _port(), _port()
    node = subprocess.Popen(["node", "-e", NODE_APP, str(node_port)])
    env = {
        **os.environ,
        "ARI_CONTROL_SECRET": SECRET,
        "ARI_ROUTES": "/payments/{id}",
        "ARI_UPSTREAM": f"http://127.0.0.1:{node_port}",
    }
    proxy = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "monitoring.proxy",
            "--listen",
            f"127.0.0.1:{proxy_port}",
            "--trust-forwarded-for",
        ],
        env=env,
        cwd=Path(__file__).resolve().parents[1],
    )
    try:
        _wait(node_port)
        _wait(proxy_port)
        yield {"base": f"http://127.0.0.1:{proxy_port}", "node_port": node_port}
    finally:
        proxy.terminate()
        node.terminate()
        proxy.wait(10)
        node.wait(10)


def _signed(base: str, payload: dict, secret: str = SECRET) -> httpx.Response:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ts, nonce = str(time.time()), secrets.token_urlsafe(16)
    canonical = f"{ts}.{nonce}.{payload['control_id']}.{hashlib.sha256(body).hexdigest()}".encode()
    headers = {
        "Content-Type": "application/json",
        "X-Ari-Timestamp": ts,
        "X-Ari-Nonce": nonce,
        "X-Ari-Control-Id": payload["control_id"],
        "X-Ari-Signature": hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest(),
    }
    return httpx.post(f"{base}/live-defense/control", content=body, headers=headers)


def test_forwards_requests_unchanged(stack) -> None:
    base = stack["base"]
    r = httpx.post(
        f"{base}/orders/7?x=1&y=2", content=b"hello", headers={"Authorization": "Bearer t"}
    )
    assert r.status_code == 200 and r.headers["x-upstream"] == "node"
    seen = r.json()
    assert seen == {
        "method": "POST",
        "url": "/orders/7?x=1&y=2",
        "body": "hello",
        "xff": "127.0.0.1",
        "auth": "Bearer t",
    }
    assert httpx.get(f"{base}/teapot").status_code == 418


def test_signed_rate_limit_applies_to_the_node_app_and_lifts(stack) -> None:
    base = stack["base"]
    applied = _signed(
        base,
        {
            "op": "apply",
            "control_id": "lct_rate1",
            "kind": "rate_limit",
            "target_type": "route",
            "target_value": "GET /payments/{id}",
            "max_requests": 2,
            "expires_at_unix": time.time() + 60,
        },
    )
    assert applied.status_code == 200 and applied.json()["ok"], applied.text
    codes = [httpx.get(f"{base}/payments/pay_{i}").status_code for i in range(3)]
    assert codes == [200, 200, 429]
    assert httpx.get(f"{base}/orders/1").status_code == 200  # other routes untouched
    inspect = _signed(base, {"op": "inspect", "control_id": "lct_rate1"}).json()
    assert inspect["present"] is True and inspect["control"]["kind"] == "rate_limit"
    assert _signed(base, {"op": "remove", "control_id": "lct_rate1"}).json()["ok"]
    assert httpx.get(f"{base}/payments/pay_9").status_code == 200


def test_source_block_uses_the_load_balancer_address_not_a_spoofed_one(stack) -> None:
    base = stack["base"]
    applied = _signed(
        base,
        {
            "op": "apply",
            "control_id": "lct_block1",
            "kind": "block_source",
            "target_type": "source_ip",
            "target_value": "203.0.113.9",
            "expires_at_unix": time.time() + 60,
        },
    )
    assert applied.json()["ok"], applied.text
    blocked = httpx.get(f"{base}/x", headers={"X-Forwarded-For": "1.2.3.4, 203.0.113.9"})
    assert blocked.status_code == 403
    spoof = httpx.get(f"{base}/x", headers={"X-Forwarded-For": "203.0.113.9, 1.2.3.4"})
    assert spoof.status_code == 200  # a client-claimed first hop is not trusted
    _signed(base, {"op": "remove", "control_id": "lct_block1"})


def test_unsigned_or_wrongly_signed_control_calls_are_refused(stack) -> None:
    base = stack["base"]
    assert (
        httpx.post(
            f"{base}/live-defense/control", json={"op": "emergency_clear", "control_id": "x"}
        ).status_code
        == 401
    )
    wrong = _signed(
        base, {"op": "emergency_clear", "control_id": "x"}, secret="hkt_ctl_" + "w" * 43
    )
    assert wrong.status_code == 401
    assert httpx.get(f"{base}/payments/p").status_code == 200


def test_ownership_proof_matches_what_ari_expects(stack) -> None:
    challenge = "abc123"
    r = _signed(
        stack["base"], {"op": "prove", "control_id": "chk_ownership", "challenge": challenge}
    )
    expected = hmac.new(SECRET.encode(), f"prove.{challenge}".encode(), hashlib.sha256).hexdigest()
    assert r.json()["proof"] == expected


def test_telemetry_reports_templates_never_raw_paths() -> None:
    from starlette.testclient import TestClient

    from monitoring.proxy import build_app

    sent: list[dict] = []

    async def upstream(request: httpx.Request) -> httpx.Response:
        status = 403 if request.url.path.endswith("denied") else 200
        return httpx.Response(status, stream=httpx.ByteStream(b"{}"))  # unread, like the network

    app = build_app(
        "http://upstream.invalid",
        control_secret=SECRET,
        templates=["/payments/{id}"],
        client=httpx.AsyncClient(transport=httpx.MockTransport(upstream)),
        send_telemetry=sent.append,
    )
    client = TestClient(app)
    client.get("/payments/pay_secret_77?card=4111")
    client.get("/payments/denied")
    client.get("/internal/raw-value-9")
    client.post("/live-defense/control", content=b"{}")
    time.sleep(1.05)  # ingest windows are at least one second long
    app.flush()  # type: ignore[attr-defined]
    routes = {r["route"]: r for r in sent[0]["routes"]}
    assert routes["GET /payments/{id}"]["requests"] == 2
    assert routes["GET /payments/{id}"]["auth_failures"] == 1
    assert routes["GET /__unmatched__"]["requests"] == 1
    assert not any("live-defense" in r for r in routes)
    wire = json.dumps(sent)
    for leaked in ("pay_secret_77", "4111", "raw-value-9"):
        assert leaked not in wire


def test_upstream_down_is_a_502() -> None:
    from starlette.testclient import TestClient

    from monitoring.proxy import build_app

    dead = f"http://127.0.0.1:{_port()}"
    client = TestClient(build_app(dead, control_secret=SECRET))
    assert client.get("/anything").status_code == 502
