"""ASGI middleware: the control endpoint Ari calls on a production application.

Runs inside the monitored application, next to ``monitoring.collector``. Standard library
only, so the file can be copied into an app that does not install this package.

Ari only calls it after an owner granted the control kind and clicked to authorize that
control. Every call is HMAC-signed with the secret Ari showed once when the channel was
registered; unsigned, stale or replayed calls are refused. Each control has an expiry
that this middleware enforces itself, so a control lapses even if Ari is down.

Controls it enforces:
  rate_limit       "METHOD /route/{template}"; at most max_requests per 60 s, then 429
  block_source     one exact client address; 403
  increase_logging sets ``logger_name`` to DEBUG until the last logging control ends
  escalate         never sent here (a human ticket inside Ari)

    app.add_middleware(AriControls, secret=os.environ["ARI_CONTROL_SECRET"])

Behind a proxy, pass ``client_ip`` that reads the address your proxy sets; the default
is the socket peer, which is the proxy itself.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import threading
import time
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass, field
from typing import Any

Scope = MutableMapping[str, Any]
CONTROL_PATH = "/live-defense/control"
REPLAY_WINDOW_S = 60.0
MAX_BODY = 16_384
KINDS = frozenset({"rate_limit", "block_source", "increase_logging"})


def _peer(scope: Scope) -> str:
    client = scope.get("client")
    return str(client[0]) if client else ""


def _route_regex(target: str) -> re.Pattern[str] | None:
    method, _, path = target.partition(" ")
    if not method or not path.startswith("/"):
        return None
    parts = re.split(r"(\{[^/{}]+\})", path)
    body = "".join("[^/]+" if p.startswith("{") else re.escape(p) for p in parts)
    return re.compile(f"{re.escape(method)} {body}")


@dataclass
class _Control:
    control_id: str
    kind: str
    target_type: str
    target_value: str
    max_requests: int | None
    expires_at: float
    route: re.Pattern[str] | None = None
    hits: list[float] = field(default_factory=list)

    def binding(self) -> tuple[Any, ...]:
        return (
            self.kind,
            self.target_type,
            self.target_value,
            self.max_requests,
            int(self.expires_at),
        )


class AriControls:
    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        *,
        secret: str,
        client_ip: Callable[[Scope], str] = _peer,
        logger_name: str = "",
        clock: Callable[[], float] = time.time,
    ) -> None:
        if len(secret) < 32:
            raise ValueError("pass the control secret Ari showed when the channel was registered")
        self.app = app
        self._secret = secret.encode()
        self._client_ip = client_ip
        self._logger = logging.getLogger(logger_name)
        self._base_level = self._logger.level
        self._clock = clock
        self._lock = threading.Lock()
        self._controls: dict[str, _Control] = {}
        self._nonces: dict[str, float] = {}
        self._reject_new = False

    async def __call__(self, scope: Scope, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        if scope.get("path") == CONTROL_PATH:
            status, doc = await self._control(scope, receive)
            await _json(send, status, doc)
            return
        refusal = self._enforce(str(scope.get("method", "")), str(scope.get("path", "")), scope)
        if refusal is not None:
            await _json(send, refusal[0], {"detail": refusal[1]})
            return
        await self.app(scope, receive, send)

    # --- enforcement -------------------------------------------------------

    def _enforce(self, method: str, path: str, scope: Scope) -> tuple[int, str] | None:
        now = self._clock()
        route = f"{method.upper()} {path}"
        with self._lock:
            self._purge(now)
            for item in self._controls.values():
                if item.kind == "block_source" and self._client_ip(scope) == item.target_value:
                    return 403, "blocked by an Ari control"
                if item.kind == "rate_limit" and item.route and item.route.fullmatch(route):
                    item.hits = [h for h in item.hits if h > now - 60.0]
                    if len(item.hits) >= (item.max_requests or 1):
                        return 429, "rate limited by an Ari control"
                    item.hits.append(now)
        return None

    def _purge(self, now: float) -> None:
        for cid in [c for c, item in self._controls.items() if item.expires_at <= now]:
            del self._controls[cid]
        for nonce in [n for n, seen in self._nonces.items() if now - seen > REPLAY_WINDOW_S]:
            del self._nonces[nonce]
        self._set_logging()

    def _set_logging(self) -> None:
        debug = any(c.kind == "increase_logging" for c in self._controls.values())
        self._logger.setLevel(logging.DEBUG if debug else self._base_level)

    # --- signed control calls ---------------------------------------------

    async def _control(self, scope: Scope, receive: Any) -> tuple[int, dict[str, Any]]:
        if scope.get("method") != "POST":
            return 405, {"ok": False, "error": "POST only"}
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if len(body) > MAX_BODY:
                return 413, {"ok": False, "error": "body too large"}
            if not message.get("more_body"):
                break
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        control_id = headers.get("x-ari-control-id", "")
        problem = self._verify(
            headers.get("x-ari-timestamp", ""),
            headers.get("x-ari-nonce", ""),
            control_id,
            headers.get("x-ari-signature", ""),
            body,
        )
        if problem:
            return 401, {"ok": False, "error": problem}
        try:
            payload = json.loads(body or b"{}")
        except ValueError:
            return 400, {"ok": False, "error": "invalid json"}
        if not isinstance(payload, dict) or str(payload.get("control_id") or "") != control_id:
            return 400, {"ok": False, "error": "control id mismatch"}
        with self._lock:
            self._purge(self._clock())
            return self._apply(payload, control_id)

    def _verify(
        self, ts: str, nonce: str, control_id: str, signature: str, body: bytes
    ) -> str | None:
        try:
            sent = float(ts)
        except ValueError:
            return "invalid timestamp"
        now = self._clock()
        if abs(now - sent) > REPLAY_WINDOW_S:
            return "timestamp outside replay window"
        canonical = f"{ts}.{nonce}.{control_id}.{hashlib.sha256(body).hexdigest()}".encode()
        expected = hmac.new(self._secret, canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return "bad signature"
        with self._lock:
            if not nonce or nonce in self._nonces:
                return "replayed or missing nonce"
            self._nonces[nonce] = now
        return None

    def _apply(self, payload: dict[str, Any], control_id: str) -> tuple[int, dict[str, Any]]:
        op = payload.get("op")
        level = logging.getLevelName(self._logger.getEffectiveLevel()).lower()
        if op == "prove":
            # Ownership challenge at channel registration: only the secret holder can answer.
            challenge = str(payload.get("challenge") or "")
            if not challenge:
                return 400, {"ok": False, "error": "challenge required"}
            proof = hmac.new(self._secret, f"prove.{challenge}".encode(), hashlib.sha256)
            return 200, {"ok": True, "proof": proof.hexdigest()}
        if op == "inspect":
            item = self._controls.get(control_id)
            return 200, {
                "ok": True,
                "present": item is not None,
                "control": None
                if item is None
                else {
                    "control_id": item.control_id,
                    "kind": item.kind,
                    "target_type": item.target_type,
                    "target_value": item.target_value,
                    "max_requests": item.max_requests,
                    "expires_at": item.expires_at,
                },
                "log_level": level,
                "reject_new": self._reject_new,
            }
        if op in ("remove", "expire"):
            existed = self._controls.pop(control_id, None) is not None
            self._set_logging()
            return 200, {"ok": True, "removed": existed, "present": False}
        if op == "emergency_clear":
            removed = sorted(self._controls)
            self._controls.clear()
            self._reject_new = True
            self._set_logging()
            return 200, {"ok": True, "removed_ids": removed, "reject_new": True}
        if op == "emergency_clear_lift":
            self._reject_new = False
            return 200, {"ok": True, "reject_new": False}
        if op != "apply":
            return 400, {"ok": False, "error": "unknown op"}
        if self._reject_new:
            return 409, {"ok": False, "error": "emergency stop: new controls rejected"}
        kind = str(payload.get("kind") or "")
        if kind not in KINDS:
            return 400, {"ok": False, "error": f"unsupported kind {kind}"}
        try:
            expires_at = float(payload["expires_at_unix"])
            max_requests = (
                None if payload.get("max_requests") is None else int(payload["max_requests"])
            )
        except (KeyError, TypeError, ValueError):
            return 400, {"ok": False, "error": "expires_at_unix / max_requests invalid"}
        item = _Control(
            control_id=control_id,
            kind=kind,
            target_type=str(payload.get("target_type") or ""),
            target_value=str(payload.get("target_value") or ""),
            max_requests=max_requests,
            expires_at=expires_at,
        )
        if kind == "rate_limit":
            item.route = _route_regex(item.target_value)
            if item.route is None:
                return 400, {"ok": False, "error": "rate_limit target must be METHOD /path"}
        existing = self._controls.get(control_id)
        if existing is not None:
            if existing.binding() != item.binding():
                return 409, {"ok": False, "error": "binding mismatch", "conflict": True}
            return 200, {"ok": True, "applied": True, "idempotent": True}
        self._controls[control_id] = item
        self._set_logging()
        return 200, {"ok": True, "applied": True, "idempotent": False}


async def _json(send: Any, status: int, doc: dict[str, Any]) -> None:
    body = json.dumps(doc).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
