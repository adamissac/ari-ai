"""Isolated owned-test HTTP fixture that enforces Phase 4 controls locally.

TTL is applied in-process on every request and does not depend on the Ari
worker remaining alive. The only unsigned traffic this process accepts is the
fixture routes; control mutations require HMAC.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from shared.live_defense import CONTROL_PATH

log = logging.getLogger("owned_test_app")
REPLAY_WINDOW_S = 60.0
FIXTURE_ROUTE = "/payments/pay_fixture"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _canonical(timestamp: str, nonce: str, control_id: str, body: bytes) -> bytes:
    digest = hashlib.sha256(body).hexdigest()
    return f"{timestamp}.{nonce}.{control_id}.{digest}".encode()


@dataclass
class StoredControl:
    control_id: str
    kind: str
    target_type: str
    target_value: str
    max_requests: int | None
    expires_at: float
    log_level: str = "info"
    hits: list[float] = field(default_factory=list)


class ControlPlane:
    def __init__(self, secret: str) -> None:
        self.secret = secret
        self.controls: dict[str, StoredControl] = {}
        self.nonces: dict[str, float] = {}
        self.reject_new = False
        self.log_level = "info"
        self._lock = threading.Lock()

    def _purge(self) -> None:
        now = time.time()
        expired = [cid for cid, item in self.controls.items() if item.expires_at <= now]
        for cid in expired:
            del self.controls[cid]
        stale = [n for n, seen in self.nonces.items() if now - seen > REPLAY_WINDOW_S]
        for nonce in stale:
            del self.nonces[nonce]

    def verify_request(
        self, timestamp: str, nonce: str, control_id: str, signature: str, body: bytes
    ) -> str | None:
        try:
            ts = float(timestamp)
        except ValueError:
            return "invalid timestamp"
        if abs(time.time() - ts) > REPLAY_WINDOW_S:
            return "timestamp outside replay window"
        if not nonce or nonce in self.nonces:
            return "replayed or missing nonce"
        expected = hmac.new(
            self.secret.encode(), _canonical(timestamp, nonce, control_id, body), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return "bad signature"
        self.nonces[nonce] = time.time()
        return None

    def apply(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        self._purge()
        if self.reject_new and payload.get("op") == "apply":
            return 409, {"ok": False, "error": "emergency stop: new controls rejected"}
        op = payload.get("op")
        control_id = str(payload.get("control_id") or "")
        if op == "inspect":
            item = self.controls.get(control_id)
            return 200, {
                "ok": True,
                "present": item is not None,
                "control": None
                if item is None
                else {
                    "control_id": item.control_id,
                    "kind": item.kind,
                    "target_value": item.target_value,
                    "expires_at": item.expires_at,
                    "log_level": item.log_level,
                },
                "log_level": self.log_level,
                "reject_new": self.reject_new,
                "active_ids": sorted(self.controls),
            }
        if op == "remove" or op == "expire":
            existed = control_id in self.controls
            self.controls.pop(control_id, None)
            return 200, {"ok": True, "removed": existed, "present": False}
        if op == "emergency_clear":
            self.reject_new = True
            removed = list(self.controls)
            self.controls.clear()
            return 200, {"ok": True, "removed_ids": removed, "reject_new": True}
        if op == "emergency_clear_lift":
            self.reject_new = False
            return 200, {"ok": True, "reject_new": False}
        if op != "apply":
            return 400, {"ok": False, "error": "unknown op"}
        if not control_id:
            return 400, {"ok": False, "error": "control_id required"}
        existing = self.controls.get(control_id)
        expires_at = float(payload.get("expires_at_unix") or (time.time() + 60))
        item = StoredControl(
            control_id=control_id,
            kind=str(payload.get("kind") or ""),
            target_type=str(payload.get("target_type") or ""),
            target_value=str(payload.get("target_value") or ""),
            max_requests=payload.get("max_requests"),
            expires_at=expires_at,
            log_level=str(payload.get("log_level") or "debug"),
        )
        if existing is not None:
            item.hits = existing.hits
        self.controls[control_id] = item
        if item.kind == "increase_logging":
            self.log_level = item.log_level
        return 200, {
            "ok": True,
            "applied": True,
            "control_id": control_id,
            "idempotent": existing is not None,
        }

    def enforce(self, method: str, path: str, source: str) -> Response | None:
        self._purge()
        route = f"{method} {path}"
        now = time.time()
        for item in self.controls.values():
            if item.kind == "block_source" and source == item.target_value:
                return JSONResponse(
                    {"detail": "source blocked by owned-test control"}, status_code=403
                )
            if item.kind == "rate_limit" and item.target_value == route:
                item.hits = [h for h in item.hits if h > now - 60.0]
                limit = int(item.max_requests or 1)
                if len(item.hits) >= limit:
                    return JSONResponse(
                        {"detail": "rate limited by owned-test control"}, status_code=429
                    )
                item.hits.append(now)
        if self.log_level == "debug":
            log.debug("owned-test %s %s source=%s", method, path, source)
        return None


def create_app(secret: str | None = None) -> FastAPI:
    secret = secret or secrets.token_urlsafe(32)
    plane = ControlPlane(secret)
    app = FastAPI(title="payments-lite owned-test control fixture", version="0.18.0")
    app.state.plane = plane
    app.state.hmac_secret = secret

    @app.middleware("http")
    async def enforce(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path == CONTROL_PATH:
            return await call_next(request)
        source = request.headers.get("x-ari-source") or (
            request.client.host if request.client else ""
        )
        blocked = plane.enforce(request.method, request.url.path, source)
        if blocked is not None:
            return blocked
        return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "environment": "OWNED TEST ENVIRONMENT"}

    @app.get(FIXTURE_ROUTE)
    def fixture_payment() -> dict[str, str]:
        return {"id": "pay_fixture", "environment": "OWNED TEST ENVIRONMENT"}

    @app.post(CONTROL_PATH)
    async def control(request: Request) -> JSONResponse:
        body = await request.body()
        ts = request.headers.get("x-ari-timestamp", "")
        nonce = request.headers.get("x-ari-nonce", "")
        control_id = request.headers.get("x-ari-control-id", "")
        signature = request.headers.get("x-ari-signature", "")
        problem = plane.verify_request(ts, nonce, control_id, signature, body)
        if problem:
            return JSONResponse({"ok": False, "error": problem}, status_code=401)
        try:
            payload = json.loads(body.decode() or "{}")
        except json.JSONDecodeError:
            return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)
        if str(payload.get("control_id") or "") != control_id:
            return JSONResponse({"ok": False, "error": "control id mismatch"}, status_code=400)
        status, doc = plane.apply(payload)
        return JSONResponse(doc, status_code=status)

    return app


def serve_in_thread(
    app: FastAPI, host: str = "127.0.0.1", port: int | None = None
) -> tuple[int, Any]:
    """Bind loopback and serve until the returned stop() is called."""
    import socket

    import uvicorn

    if port is None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, 0))
        port = int(sock.getsockname()[1])
        sock.close()
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 5
    while time.time() < deadline and not getattr(server, "started", False):
        time.sleep(0.05)
    if not getattr(server, "started", False):
        raise RuntimeError("owned-test fixture failed to start")

    def stop() -> None:
        server.should_exit = True
        thread.join(timeout=5)

    return port, stop


def main(argv: list[str] | None = None) -> int:
    """Serve the owned-test fixture on loopback. HMAC secret from --secret or env."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Owned-test Live Defense control fixture")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--secret", default=os.environ.get("OWNED_TEST_HMAC_SECRET", ""))
    args = parser.parse_args(argv)
    if args.host != "127.0.0.1":
        raise SystemExit("owned-test fixture binds loopback only")
    if not args.secret:
        raise SystemExit("pass --secret or OWNED_TEST_HMAC_SECRET (shown once by Ari)")
    app = create_app(args.secret)
    port, stop = serve_in_thread(app, host=args.host, port=args.port)
    print(f"OWNED TEST ENVIRONMENT fixture on http://127.0.0.1:{port}{CONTROL_PATH}", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
