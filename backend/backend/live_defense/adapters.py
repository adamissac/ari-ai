"""Typed control adapter for the owner's registered control endpoint.

The platform never touches infrastructure directly. It asks the application the owner
connected to apply, read or remove one control, over HTTP signed with that
application's secret:

    POST   {control_url}/controls                 {control_id, kind, target, expires_at, ...}
    GET    {control_url}/controls/{control_id}
    POST   {control_url}/controls/{control_id}/remove

Headers: ``X-Ari-App``, ``X-Ari-Timestamp`` (unix seconds) and ``X-Ari-Signature`` =
``sha256=HMAC(secret, timestamp + "." + METHOD + " " + PATH + "\\n" + BODY)``. The control
id is the action id, so a retried apply upserts the same control (idempotent). All calls
go through ``netguard`` (resolved-address checks, pinned connection, no redirects).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from backend.live_defense import netguard, vault


@dataclass(frozen=True)
class ControlResult:
    ok: bool
    state: str  # active | absent | removed | error
    http_status: int | None
    detail: str
    retryable: bool

    def summary(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "state": self.state,
            "http_status": self.http_status,
            "detail": self.detail[:300],
        }


def canonical(method: str, path: str, body: bytes) -> bytes:
    return f"{method} {path}\n".encode() + body


def _call(
    app_id: str, secret: str, method: str, url: str, body: dict[str, Any] | None
) -> httpx.Response:
    raw = (
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        if body is not None
        else b""
    )
    path = urlsplit(url).path or "/"
    ts = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-Ari-App": app_id,
        "X-Ari-Timestamp": ts,
        "X-Ari-Signature": vault.sign(secret, ts, canonical(method, path, raw)),
    }
    return netguard.request(method, url, content=raw, headers=headers)


def _base(control_url: str) -> str:
    return control_url.rstrip("/")


def _result(resp: httpx.Response, ok_state: str) -> ControlResult:
    if 300 <= resp.status_code < 400:
        return ControlResult(False, "error", resp.status_code, "redirect refused", False)
    if resp.status_code >= 500:
        return ControlResult(False, "error", resp.status_code, resp.text[:300], True)
    if resp.status_code == 404:
        return ControlResult(False, "absent", 404, "control not found on the application", False)
    if resp.status_code >= 400:
        return ControlResult(False, "error", resp.status_code, resp.text[:300], False)
    try:
        state = str(resp.json().get("state", ok_state))
    except ValueError:
        state = ok_state
    return ControlResult(True, state, resp.status_code, "ok", False)


def _guarded(fn: Any) -> ControlResult:
    try:
        return fn()
    except netguard.UnsafeDestination as exc:
        return ControlResult(False, "error", None, f"destination refused: {exc}", False)
    except httpx.HTTPError as exc:
        return ControlResult(False, "error", None, f"{type(exc).__name__}: {exc}"[:300], True)
    except vault.SecretKeyUnavailable as exc:
        return ControlResult(False, "error", None, str(exc), False)


def apply(app: dict[str, Any], action: dict[str, Any]) -> ControlResult:
    def go() -> ControlResult:
        secret = vault.decrypt(app["secret_ciphertext"])
        body = {
            "control_id": action["id"],
            "incident_id": action["incident_id"],
            "kind": action["kind"],
            "target": action["target"],
            "duration_s": action["duration_s"],
            "expires_at": action["expires_at"],
        }
        return _result(
            _call(app["id"], secret, "POST", _base(app["control_url"]) + "/controls", body),
            "active",
        )

    return _guarded(go)


def status(app: dict[str, Any], control_id: str) -> ControlResult:
    def go() -> ControlResult:
        secret = vault.decrypt(app["secret_ciphertext"])
        url = f"{_base(app['control_url'])}/controls/{control_id}"
        return _result(_call(app["id"], secret, "GET", url, None), "active")

    return _guarded(go)


def remove(app: dict[str, Any], control_id: str, reason: str) -> ControlResult:
    def go() -> ControlResult:
        secret = vault.decrypt(app["secret_ciphertext"])
        url = f"{_base(app['control_url'])}/controls/{control_id}/remove"
        res = _result(_call(app["id"], secret, "POST", url, {"reason": reason[:200]}), "removed")
        if not res.ok and res.state == "absent":  # already gone: removal is complete
            return ControlResult(True, "removed", res.http_status, "already absent", False)
        return res

    return _guarded(go)
