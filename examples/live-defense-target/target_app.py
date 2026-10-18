"""Owned test application for the Live Defense demonstration ("Lumen Shop", test only).

A tiny web app the team owns and runs locally. It is the ONLY system Ari's live
defense acts on in the demo. It:

* serves ``POST /login`` and ``GET /items/{id}`` (the surface the controlled test traffic
  exercises);
* reports its own security telemetry to Ari (``POST /api/v1/ingest/live/{app_id}`` with
  its ingest token): failed sign-ins, missing routes, server errors and requests it
  refused because of an active control (``blocked``);
* exposes a signed control API under ``/ari`` that Ari calls to apply, read and remove
  reversible controls (block one source address, rate-limit one route, raise logging);
  every control also expires locally at its ``expires_at``;
* receives Ari's signed owner notifications at ``/ari/notifications``.

Traffic that carries ``X-Ari-Test-Traffic: 1`` is reported with ``controlled_test=true``.
Client addresses come from ``X-Forwarded-For`` (``TRUST_FORWARDED=1``, test only) so the
demo can use RFC 5737 documentation addresses (203.0.113.0/24) instead of real hosts.

Run:  ARI_CONFIG=~/.cache/ari-live-defense-demo.json uvicorn target_app:app --port 8765
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("live_defense_target")
SKEW_S = 300
USERS = {"demo@lumen.test": "correct horse battery staple"}


@dataclass
class Config:
    app_id: str = ""
    ingest_url: str = ""
    ingest_token: str = ""
    signing_secret: str = ""
    trust_forwarded: bool = True
    flush_interval_s: float = 0.5

    @classmethod
    def load(cls) -> Config:
        path = os.environ.get("ARI_CONFIG")
        data: dict[str, Any] = json.loads(Path(path).expanduser().read_text()) if path else {}
        return cls(
            app_id=data.get("app_id") or os.environ.get("ARI_APP_ID", ""),
            ingest_url=data.get("ingest_url") or os.environ.get("ARI_INGEST_URL", ""),
            ingest_token=data.get("ingest_token") or os.environ.get("ARI_INGEST_TOKEN", ""),
            signing_secret=data.get("signing_secret") or os.environ.get("ARI_SIGNING_SECRET", ""),
            trust_forwarded=os.environ.get("TRUST_FORWARDED", "1") == "1",
        )


@dataclass
class Control:
    id: str
    kind: str
    target: str
    expires_at: datetime
    removed: bool = False

    def active(self) -> bool:
        return not self.removed and datetime.now(UTC) < self.expires_at


@dataclass
class State:
    controls: dict[str, Control] = field(default_factory=dict)
    outbox: list[dict[str, Any]] = field(default_factory=list)
    notifications: list[dict[str, Any]] = field(default_factory=list)
    sent: int = 0
    send_errors: int = 0
    last_send_error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


def canonical(method: str, path: str, body: bytes) -> bytes:
    return f"{method} {path}\n".encode() + body


def signature(secret: str, ts: str, payload: bytes) -> str:
    return (
        "sha256="
        + hmac.new(secret.encode(), ts.encode() + b"." + payload, hashlib.sha256).hexdigest()
    )


def create_app(config: Config | None = None) -> FastAPI:
    cfg = config or Config.load()
    st = State()
    app = FastAPI(title="Lumen Shop (owned test application)")
    app.state.live = st
    app.state.cfg = cfg

    def emit(kind: str, request: Request, ip: str, status: int, detail: str | None = None) -> None:
        event = {
            "event_id": f"lumen-{uuid.uuid4().hex}",
            "kind": kind,
            "occurred_at": datetime.now(UTC).isoformat(),
            "source_ip": ip,
            "route": f"{request.method} {getattr(request.scope.get('route'), 'path', request.url.path)}",
            "status": status,
            "controlled_test": request.headers.get("x-ari-test-traffic") == "1",
            "detail": detail,
        }
        with st.lock:
            st.outbox.append(event)

    def client_ip(request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for")
        if cfg.trust_forwarded and fwd:
            return fwd.split(",")[0].strip()
        return request.client.host if request.client else "0.0.0.0"

    def verified(request: Request, body: bytes) -> bool:
        if not cfg.signing_secret:
            return False
        ts = request.headers.get("x-ari-timestamp", "")
        if not ts.isdigit() or abs(time.time() - int(ts)) > SKEW_S:
            return False
        expected = signature(
            cfg.signing_secret, ts, canonical(request.method, request.url.path, body)
        )
        return hmac.compare_digest(expected, request.headers.get("x-ari-signature", ""))

    def refused(request: Request, ip: str) -> JSONResponse | None:
        route = f"{request.method} {request.url.path}"
        for c in list(st.controls.values()):
            if not c.active():
                continue
            if c.kind == "block_source" and c.target == ip:
                emit("blocked", request, ip, 403, f"blocked by control {c.id}")
                return JSONResponse(
                    {"error": "blocked by an active security control"}, status_code=403
                )
            if c.kind == "rate_limit" and c.target == route:
                emit("blocked", request, ip, 429, f"rate-limited by control {c.id}")
                return JSONResponse({"error": "rate limited"}, status_code=429)
        return None

    @app.middleware("http")
    async def enforce(request: Request, call_next: Any) -> Any:
        if request.url.path.startswith("/ari") or request.url.path == "/health":
            return await call_next(request)
        ip = client_ip(request)
        if (resp := refused(request, ip)) is not None:
            return resp
        response = await call_next(request)
        if response.status_code == 404:
            emit("not_found", request, ip, 404)
        elif response.status_code >= 500:
            emit("server_error", request, ip, response.status_code)
        return response

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "app": "lumen-shop", "environment": "owned_test"}

    @app.post("/login")
    async def login(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except ValueError:
            body = {}
        user, password = str(body.get("username", "")), str(body.get("password", ""))
        ip = client_ip(request)
        if USERS.get(user) == password:
            emit("request", request, ip, 200, "sign-in succeeded")
            return JSONResponse({"ok": True})
        emit("auth_failure", request, ip, 401, "wrong username or password")
        return JSONResponse({"error": "invalid credentials"}, status_code=401)

    @app.get("/items/{item_id}")
    def item(item_id: int) -> dict[str, Any]:
        return {"id": item_id, "name": f"Item {item_id}"}

    # ---------------------------------------------------------- Ari control API (signed)

    @app.post("/ari/controls")
    async def apply_control(request: Request) -> JSONResponse:
        raw = await request.body()
        if not verified(request, raw):
            return JSONResponse({"error": "bad signature"}, status_code=401)
        data = json.loads(raw)
        if data.get("kind") not in ("block_source", "rate_limit", "increase_logging"):
            return JSONResponse({"error": "unsupported control"}, status_code=422)
        control = Control(
            id=data["control_id"],
            kind=data["kind"],
            target=data.get("target") or "*",
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )
        with st.lock:
            st.controls[control.id] = control  # upsert by id: a retried apply is idempotent
        log.info(
            "control %s applied: %s %s until %s",
            control.id,
            control.kind,
            control.target,
            control.expires_at,
        )
        return JSONResponse({"control_id": control.id, "state": "active"}, status_code=201)

    @app.get("/ari/controls/{control_id}")
    async def read_control(control_id: str, request: Request) -> JSONResponse:
        if not verified(request, b""):
            return JSONResponse({"error": "bad signature"}, status_code=401)
        c = st.controls.get(control_id)
        if c is None:
            return JSONResponse({"error": "unknown control"}, status_code=404)
        state = "active" if c.active() else ("removed" if c.removed else "expired")
        return JSONResponse(
            {"control_id": c.id, "state": state, "expires_at": c.expires_at.isoformat()}
        )

    @app.post("/ari/controls/{control_id}/remove")
    async def remove_control(control_id: str, request: Request) -> JSONResponse:
        raw = await request.body()
        if not verified(request, raw):
            return JSONResponse({"error": "bad signature"}, status_code=401)
        c = st.controls.get(control_id)
        if c is None:
            return JSONResponse({"error": "unknown control"}, status_code=404)
        c.removed = True
        return JSONResponse({"control_id": c.id, "state": "removed"})

    @app.post("/ari/notifications")
    async def receive_notification(request: Request) -> JSONResponse:
        raw = await request.body()
        if not verified(request, raw):
            return JSONResponse({"error": "bad signature"}, status_code=401)
        with st.lock:
            st.notifications.append(
                {
                    "received_at": datetime.now(UTC).isoformat(),
                    "event": request.headers.get("x-ari-event"),
                    **json.loads(raw),
                }
            )
        return JSONResponse({"ok": True})

    @app.get("/ari/state")
    def state() -> dict[str, Any]:
        return {
            "controls": [
                {
                    "id": c.id,
                    "kind": c.kind,
                    "target": c.target,
                    "active": c.active(),
                    "expires_at": c.expires_at.isoformat(),
                }
                for c in st.controls.values()
            ],
            "notifications": st.notifications[-50:],
            "telemetry": {
                "sent": st.sent,
                "queued": len(st.outbox),
                "errors": st.send_errors,
                "last_error": st.last_send_error,
            },
        }

    def flush_once() -> int:
        if not cfg.ingest_url:
            return 0
        with st.lock:
            batch, st.outbox = st.outbox[:200], st.outbox[200:]
        if not batch:
            return 0
        try:
            r = httpx.post(
                cfg.ingest_url,
                json={"events": batch},
                headers={"Authorization": f"Bearer {cfg.ingest_token}"},
                timeout=5,
            )
            if r.status_code >= 300:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            st.sent += len(batch)
            return len(batch)
        except Exception as exc:  # keep events; the next flush retries (dedupe by event_id)
            st.send_errors += 1
            st.last_send_error = str(exc)[:300]
            with st.lock:
                st.outbox = batch + st.outbox
            return 0

    app.state.flush_once = flush_once

    def loop() -> None:
        while True:
            time.sleep(cfg.flush_interval_s)
            flush_once()

    @app.on_event("startup")
    def start_flusher() -> None:
        if os.environ.get("TARGET_NO_FLUSHER") != "1":
            threading.Thread(target=loop, daemon=True, name="telemetry-flusher").start()

    return app


app = create_app() if os.environ.get("ARI_CONFIG") or os.environ.get("ARI_APP_ID") else None
