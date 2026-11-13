"""HMAC-signed HTTP adapter.

Two destinations only: the loopback owned-test fixture (http://127.0.0.1) and a production
application's own control endpoint (https, public address, fixed path). Production calls
resolve DNS once, refuse any non-public address, and connect to that exact address with TLS
verified against the registered hostname, so a DNS change cannot redirect the call inward.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from shared.live_defense import (
    CONTROL_PATH,
    ControlChannelView,
    LiveControlKind,
    is_owned_test_block_source,
)

ALLOWED_HOSTS = frozenset({"127.0.0.1"})
CONNECT_TIMEOUT_S = 2.0
PRODUCTION_TIMEOUT_S = 5.0
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


def public_address(value: str) -> bool:
    """A single global unicast address. Private, loopback, link-local, multicast,
    reserved, documentation and IPv4-mapped forms are all refused."""
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return False
    return addr.is_global and not addr.is_multicast


def _resolve(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({str(info[4][0]) for info in infos})


def production_host_shape(host: str) -> str | None:
    """No-DNS check the gate can run. Returns the literal address when ``host`` is one."""
    lowered = host.lower().strip("[]")
    if not lowered or lowered == "localhost" or lowered.endswith((".local", ".internal")):
        raise AdapterDenied("control host is not a public hostname")
    try:
        literal = ipaddress.ip_address(lowered)
    except ValueError:
        if "." not in lowered:
            raise AdapterDenied("control host is not a public hostname") from None
        return None
    if not public_address(str(literal)):
        raise AdapterDenied("control host is not a public address")
    return str(literal)


def production_host_ok(host: str, port: int) -> str:
    """Resolve ``host`` and return the address to connect to. Every resolved address must
    be public; one internal answer refuses the whole host."""
    literal = production_host_shape(host)
    if literal is not None:
        return literal
    try:
        addresses = _resolve(host, port)
    except OSError as exc:
        raise AdapterDenied(f"control host does not resolve: {type(exc).__name__}") from exc
    if not addresses or not all(public_address(a) for a in addresses):
        raise AdapterDenied("control host resolves to a non-public address")
    return addresses[0]


def parse_production_url(url: str) -> tuple[str, int]:
    """Validate an owner-supplied production control URL. Returns (host, port)."""
    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        raise AdapterDenied("production control URL must use https")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.params:
        raise AdapterDenied("userinfo, query, and fragment are denied")
    if parsed.path != CONTROL_PATH:
        raise AdapterDenied(f"path must be {CONTROL_PATH}")
    host = (parsed.hostname or "").lower()
    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise AdapterDenied("port is not valid") from exc
    production_host_ok(host, port)
    return host, port


def channel_url(view: ControlChannelView) -> str:
    if view.scheme == "https":
        host = f"[{view.host}]" if ":" in view.host else view.host
        return f"https://{host}:{view.port}{CONTROL_PATH}"
    return registered_control_url(view.host, view.port)


def assert_ssrf_safe(url: str) -> tuple[str, int, str]:
    """Loopback fixture URL check (http only)."""
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


def _send(
    url: str, body: bytes, headers: dict[str, str], timeout_s: float, sni_hostname: str | None
) -> httpx.Response:
    extensions = {"sni_hostname": sni_hostname} if sni_hostname else None
    with httpx.Client(timeout=timeout_s, follow_redirects=False, trust_env=False) as client:
        return client.post(url, content=body, headers=headers, extensions=extensions)


def call(
    url: str,
    secret: str,
    payload: dict[str, Any],
    *,
    timeout_s: float = CONNECT_TIMEOUT_S,
) -> AdapterResult:
    parsed = urlparse(url)
    sni: str | None = None
    if parsed.scheme == "https":
        host, port = parse_production_url(url)
        address = production_host_ok(host, port)
        netloc = f"[{address}]" if ":" in address else address
        target = f"https://{netloc}:{port}{CONTROL_PATH}"
        sni = host
        timeout_s = max(timeout_s, PRODUCTION_TIMEOUT_S)
    else:
        host, port, _path = assert_ssrf_safe(url)
        target = registered_control_url(host, port)
        if target != url:
            raise AdapterDenied("URL is not the reconstructed registered URL")
        if (
            payload.get("op") == "apply"
            and str(payload.get("kind") or "") == LiveControlKind.block_source.value
            and not is_owned_test_block_source(str(payload.get("target_value") or ""))
        ):
            raise AdapterDenied("block_source target is not an owned-test fixture IP")
    control_id = str(payload.get("control_id") or "")
    if not control_id:
        raise AdapterDenied("control_id is required")
    if (
        sni
        and payload.get("op") == "apply"
        and str(payload.get("kind") or "") == LiveControlKind.block_source.value
        and not public_address(str(payload.get("target_value") or ""))
    ):
        raise AdapterDenied("block_source target is not a single public address")
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
    if sni:
        headers["Host"] = host if port == 443 else f"{host}:{port}"
    try:
        response = _send(target, body, headers, timeout_s, sni)
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
