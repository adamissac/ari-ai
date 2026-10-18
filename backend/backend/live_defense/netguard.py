"""SSRF-safe outbound HTTP for owner-supplied URLs (control endpoints, notification webhooks).

String checks alone are not enough: a public-looking hostname can resolve to 127.0.0.1,
to an internal service or to a cloud metadata address, and can change between the check
and the connection (DNS rebinding). So every request:

1. parses the URL strictly (http/https only, no credentials, no fragment);
2. resolves the host and rejects it unless EVERY resolved address is public, except an
   exact ``host:port`` the operator listed in ``LIVE_DEFENSE_ALLOWED_PRIVATE_HOSTS``
   (an owned test app on loopback/private space). Link-local, multicast, unspecified,
   reserved and cloud metadata addresses are never allowed, allowlisted or not;
3. connects to the address it validated (the URL is rewritten to the IP literal, the
   original ``Host`` header and TLS SNI/certificate hostname are kept), so a second DNS
   answer cannot redirect the connection;
4. never follows redirects (a 3xx is returned to the caller, which treats it as failure);
5. bounds the timeout and the response size.

Plain http is accepted only for allowlisted private hosts or in development/test.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import httpx

from backend.settings import get_settings

MAX_RESPONSE_BYTES = 64 * 1024

# Cloud instance metadata and similar control-plane addresses: never reachable.
METADATA_ADDRESSES = frozenset(
    ipaddress.ip_address(a)
    for a in (
        "169.254.169.254",  # AWS / GCP / Azure / OpenStack IMDS
        "169.254.170.2",  # AWS ECS task metadata
        "169.254.169.253",  # AWS Route 53 resolver
        "100.100.100.200",  # Alibaba Cloud metadata
        "fd00:ec2::254",  # AWS IMDS over IPv6
    )
)

Resolver = Callable[[str, int], list[str]]


class UnsafeDestination(ValueError):
    """The URL or one of its resolved addresses is not an allowed destination."""


@dataclass(frozen=True)
class Destination:
    scheme: str
    host: str
    port: int
    path_query: str
    address: str  # the validated IP the connection will use


def _system_resolver(host: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeDestination(f"cannot resolve {host}") from exc
    return sorted({str(info[4][0]).split("%", 1)[0] for info in infos})


RESOLVER: Resolver = _system_resolver  # tests replace this to simulate DNS answers


def allowed_private_hosts() -> frozenset[str]:
    raw = get_settings().live_defense_allowed_private_hosts
    return frozenset(p.strip().lower() for p in raw.split(",") if p.strip())


def _address_problem(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address, allowlisted: bool
) -> str | None:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _address_problem(ip.ipv4_mapped, allowlisted)
    if ip in METADATA_ADDRESSES:
        return "cloud metadata address"
    if ip.is_link_local:
        return "link-local address"
    if ip.is_multicast:
        return "multicast address"
    if ip.is_unspecified:
        return "unspecified address"
    if ip.is_reserved:
        return "reserved address"
    if ip.is_loopback or ip.is_private or not ip.is_global:
        return None if allowlisted else "loopback or private address"
    return None


def check_url(url: str, *, resolve: bool = True) -> Destination:
    try:
        parts = urlsplit(url.strip())
    except ValueError as exc:
        raise UnsafeDestination("malformed URL") from exc
    if parts.scheme not in ("http", "https"):
        raise UnsafeDestination("only http and https URLs are allowed")
    if parts.username is not None or parts.password is not None:
        raise UnsafeDestination("credentials in URLs are not allowed")
    if parts.fragment:
        raise UnsafeDestination("fragments are not allowed")
    host = (parts.hostname or "").lower()
    if not host:
        raise UnsafeDestination("URL has no host")
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeDestination("invalid port") from exc
    allowlisted = f"{host}:{port}" in allowed_private_hosts()
    if parts.scheme == "http" and not allowlisted and not get_settings().is_dev:
        raise UnsafeDestination("https is required outside development for non-allowlisted hosts")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        addresses = [str(literal)]
    elif not resolve:
        addresses = []
    else:
        addresses = RESOLVER(host, port)
        if not addresses:
            raise UnsafeDestination(f"{host} resolved to no addresses")
    for address in addresses:
        problem = _address_problem(ipaddress.ip_address(address), allowlisted)
        if problem:
            raise UnsafeDestination(f"{host} resolves to a {problem} ({address})")
    path_query = urlunsplit(("", "", parts.path or "/", parts.query, ""))
    return Destination(parts.scheme, host, port, path_query, addresses[0] if addresses else "")


def request(
    method: str,
    url: str,
    *,
    content: bytes = b"",
    headers: dict[str, str] | None = None,
    timeout_s: float | None = None,
) -> httpx.Response:
    """One pinned, non-redirecting request. Raises ``UnsafeDestination`` or ``httpx.HTTPError``."""
    dest = check_url(url)
    ip = ipaddress.ip_address(dest.address)
    netloc = f"[{ip}]" if ip.version == 6 else str(ip)
    default = 443 if dest.scheme == "https" else 80
    host_header = dest.host if dest.port == default else f"{dest.host}:{dest.port}"
    pinned = f"{dest.scheme}://{netloc}:{dest.port}{dest.path_query}"
    send_headers = {**(headers or {}), "Host": host_header}
    extensions = {"sni_hostname": dest.host} if dest.scheme == "https" else {}
    timeout = timeout_s or get_settings().live_defense_http_timeout_s
    with httpx.Client(follow_redirects=False, timeout=timeout, trust_env=False) as client:
        req = client.build_request(
            method, pinned, content=content, headers=send_headers, extensions=extensions
        )
        resp = client.send(req, stream=True)
        try:
            body = b""
            for chunk in resp.iter_bytes():
                body += chunk
                if len(body) > MAX_RESPONSE_BYTES:
                    raise UnsafeDestination("response exceeds 64 KiB")
        finally:
            resp.close()
        kept = {k: v for k, v in resp.headers.items() if k.lower() == "content-type"}
        return httpx.Response(resp.status_code, headers=kept, content=body, request=req)
