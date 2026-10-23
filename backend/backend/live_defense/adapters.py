"""HMAC-signed HTTP adapter. Talks only to a registered loopback control URL."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from shared.live_defense import CONTROL_PATH

ALLOWED_HOSTS = frozenset({"127.0.0.1"})
CONNECT_TIMEOUT_S = 2.0
REPLAY_NONCE_BYTES = 16


class AdapterDenied(ValueError):
    """SSRF / allowlist failure. Fail closed; do not send the request."""


@dataclass(frozen=True)
class AdapterResult:
    ok: bool
    http_status: int | None
    body: dict[str, Any]
    error: str | None = None


def registered_control_url(host: str, port: int) -> str:
    if host not in ALLOWED_HOSTS:
        raise AdapterDenied("host is not the owned-test loopback fixture")
    if port < 1024 or port > 65535:
        raise AdapterDenied("port is not in the registered range")
    return f"http://{host}:{port}{CONTROL_PATH}"


def assert_ssrf_safe(url: str) -> tuple[str, int, str]:
    parsed = urlparse(url)
    if parsed.scheme != "http":
        raise AdapterDenied("only http to loopback is allowed for the owned-test fixture")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AdapterDenied("userinfo, query, and fragment are denied")
    if parsed.hostname not in ALLOWED_HOSTS:
        raise AdapterDenied("host is not the owned-test loopback fixture")
    if parsed.path != CONTROL_PATH:
        raise AdapterDenied("path is not the fixed control path")
    port = parsed.port
    if port is None or port < 1024 or port > 65535:
        raise AdapterDenied("port is not in the registered range")
    # No DNS: we already required the literal hostname 127.0.0.1.
    return parsed.hostname or "", port, parsed.path


def sign(secret: str, *, timestamp: str, nonce: str, control_id: str, body: bytes) -> str:
    digest = hashlib.sha256(body).hexdigest()
    canonical = f"{timestamp}.{nonce}.{control_id}.{digest}".encode()
    return hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()


def call(
    url: str,
    secret: str,
    payload: dict[str, Any],
    *,
    timeout_s: float = CONNECT_TIMEOUT_S,
) -> AdapterResult:
    host, port, path = assert_ssrf_safe(url)
    _ = path
    bound = registered_control_url(host, port)
    if bound != url:
        raise AdapterDenied("URL is not the reconstructed registered URL")
    control_id = str(payload.get("control_id") or "")
    if not control_id:
        raise AdapterDenied("control_id is required")
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    timestamp = str(time.time())
    nonce = secrets.token_urlsafe(REPLAY_NONCE_BYTES)
    signature = sign(secret, timestamp=timestamp, nonce=nonce, control_id=control_id, body=body)
    headers = {
        "Content-Type": "application/json",
        "X-Ari-Timestamp": timestamp,
        "X-Ari-Nonce": nonce,
        "X-Ari-Control-Id": control_id,
        "X-Ari-Signature": signature,
    }
    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=False, trust_env=False) as client:
            response = client.post(bound, content=body, headers=headers)
    except httpx.HTTPError as exc:
        return AdapterResult(ok=False, http_status=None, body={}, error=type(exc).__name__)
    try:
        parsed_body = response.json()
        if not isinstance(parsed_body, dict):
            parsed_body = {"raw": parsed_body}
    except ValueError:
        parsed_body = {}
    return AdapterResult(
        ok=response.status_code == 200 and bool(parsed_body.get("ok")),
        http_status=response.status_code,
        body=parsed_body,
        error=None if response.status_code == 200 else f"http_{response.status_code}",
    )
