"""Ari Live Defense sidecar: a reverse proxy in front of an application in any language.

Put it between your load balancer and your app. It forwards every request unchanged and adds:
  * telemetry (``monitoring.collector``): per-route counters to Ari, route templates only;
  * controls (``monitoring.controls``): Ari's signed control endpoint at
    ``/live-defense/control`` and enforcement of rate limits, source blocks and logging.

    ARI_UPSTREAM=http://127.0.0.1:3000          # your app
    ARI_CONTROL_SECRET=hkt_ctl_...               # shown once when you registered the channel
    ARI_API_BASE=https://<ari api host>          # telemetry; all three or none
    ARI_PROJECT_ID=prj_...
    ARI_INGEST_TOKEN=hkt_ing_...                 # application-bound ingest token
    ARI_ROUTES=/payments/{id},/users/{id}/orders # or --routes FILE, one template per line
    python -m monitoring.proxy --listen 0.0.0.0:8080

Behind a platform load balancer, pass ``--trust-forwarded-for`` so a source block applies to
the address the load balancer saw (the last ``X-Forwarded-For`` entry), not to the balancer.
Without it, blocks apply to the socket peer. WebSockets are not proxied.
"""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

import httpx

from monitoring.collector import AriCollector
from monitoring.controls import CONTROL_PATH, AriControls

Scope = MutableMapping[str, Any]
log = logging.getLogger("ari.proxy")

MAX_BODY = 10 * 1024 * 1024
HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
    }
)


def _peer(scope: Scope) -> str:
    client = scope.get("client")
    return str(client[0]) if client else ""


def forwarded_client(scope: Scope) -> str:
    """Last X-Forwarded-For entry: the address the trusted load balancer itself saw.
    Earlier entries are whatever the client claimed and are ignored."""
    for name, value in scope.get("headers", []):
        if name.lower() == b"x-forwarded-for":
            last = value.decode("latin-1").split(",")[-1].strip()
            if last:
                return last
    return _peer(scope)


class Upstream:
    """Minimal ASGI reverse proxy. Streams the response; buffers the request (bounded)."""

    def __init__(
        self,
        upstream: str,
        *,
        client: httpx.AsyncClient | None = None,
        max_body: int = MAX_BODY,
        on_shutdown: list[Callable[[], None]] | None = None,
    ) -> None:
        self._base = upstream.rstrip("/")
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0), follow_redirects=False, trust_env=False
        )
        self._max_body = max_body
        self.on_shutdown = on_shutdown if on_shutdown is not None else []

    async def __call__(self, scope: Scope, receive: Any, send: Any) -> None:
        if scope["type"] == "lifespan":
            await self._lifespan(receive, send)
            return
        if scope["type"] != "http":
            return  # websockets are not proxied; the server closes the connection
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if len(body) > self._max_body:
                await _plain(send, 413, b"request body too large")
                return
            if not message.get("more_body"):
                break
        path = scope.get("raw_path") or scope["path"].encode()
        query = scope.get("query_string", b"")
        url = self._base + path.decode("latin-1") + (f"?{query.decode('latin-1')}" if query else "")
        headers = [
            (k.decode("latin-1"), v.decode("latin-1"))
            for k, v in scope.get("headers", [])
            if k.decode("latin-1").lower() not in HOP_BY_HOP
        ]
        peer = _peer(scope)
        prior = next((v for k, v in headers if k.lower() == "x-forwarded-for"), "")
        headers = [(k, v) for k, v in headers if k.lower() != "x-forwarded-for"]
        headers.append(("x-forwarded-for", f"{prior}, {peer}" if prior else peer))
        request = self._client.build_request(scope["method"], url, headers=headers, content=body)
        try:
            response = await self._client.send(request, stream=True)
        except httpx.HTTPError as exc:
            log.warning("upstream unreachable: %s", type(exc).__name__)
            await _plain(send, 502, b"upstream unreachable")
            return
        try:
            await send(
                {
                    "type": "http.response.start",
                    "status": response.status_code,
                    "headers": [
                        (k.encode("latin-1"), v.encode("latin-1"))
                        for k, v in response.headers.multi_items()
                        if k.lower() not in HOP_BY_HOP
                    ],
                }
            )
            async for chunk in response.aiter_raw():
                await send({"type": "http.response.body", "body": chunk, "more_body": True})
            await send({"type": "http.response.body", "body": b""})
        finally:
            await response.aclose()

    async def _lifespan(self, receive: Any, send: Any) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                for hook in self.on_shutdown:
                    try:
                        hook()
                    except Exception:  # noqa: BLE001 — shutdown must finish
                        log.warning("shutdown hook failed", exc_info=True)
                await self._client.aclose()
                await send({"type": "lifespan.shutdown.complete"})
                return


async def _plain(send: Any, status: int, body: bytes) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"text/plain"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def build_app(
    upstream: str,
    *,
    control_secret: str | None,
    api_base: str | None = None,
    project_id: str | None = None,
    ingest_token: str | None = None,
    templates: list[str] | None = None,
    trust_forwarded_for: bool = False,
    client: httpx.AsyncClient | None = None,
    send_telemetry: Callable[[dict[str, Any]], None] | None = None,
) -> Callable[..., Awaitable[None]]:
    """Collector outermost (it also counts 429/403 answers), then controls, then the app."""
    proxy = Upstream(upstream, client=client)
    app: Callable[..., Awaitable[None]] = proxy
    if control_secret:
        app = AriControls(
            app,
            secret=control_secret,
            client_ip=forwarded_client if trust_forwarded_for else _peer,
        )
    if send_telemetry or (api_base and project_id and ingest_token):
        collector = AriCollector(
            app,
            api_base=api_base or "",
            project_id=project_id or "",
            token=ingest_token or "",
            templates=templates,
            send=send_telemetry,
            skip_paths=(CONTROL_PATH,),
        )
        proxy.on_shutdown.append(collector.flush)
        app = collector
    return app


def _templates(path: str | None) -> list[str]:
    items = [t for t in os.environ.get("ARI_ROUTES", "").split(",") if t.strip()]
    if path:
        with open(path, encoding="utf-8") as fh:
            items += [
                line for line in fh.read().splitlines() if line.strip() and not line.startswith("#")
            ]
    return items


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    parser = argparse.ArgumentParser(description="Ari Live Defense sidecar proxy")
    parser.add_argument("--listen", default=os.environ.get("ARI_LISTEN", "0.0.0.0:8080"))
    parser.add_argument("--upstream", default=os.environ.get("ARI_UPSTREAM", ""))
    parser.add_argument("--routes", default=os.environ.get("ARI_ROUTES_FILE"))
    parser.add_argument("--trust-forwarded-for", action="store_true")
    args = parser.parse_args(argv)
    if not args.upstream.startswith(("http://", "https://")):
        raise SystemExit("set --upstream or ARI_UPSTREAM to your app, e.g. http://127.0.0.1:3000")
    secret = os.environ.get("ARI_CONTROL_SECRET") or None
    telemetry = [os.environ.get(k) for k in ("ARI_API_BASE", "ARI_PROJECT_ID", "ARI_INGEST_TOKEN")]
    if any(telemetry) and not all(telemetry):
        raise SystemExit("set all of ARI_API_BASE, ARI_PROJECT_ID, ARI_INGEST_TOKEN, or none")
    if not secret and not all(telemetry):
        raise SystemExit(
            "nothing to do: set ARI_CONTROL_SECRET and/or the ARI_* telemetry settings"
        )
    app = build_app(
        args.upstream,
        control_secret=secret,
        api_base=telemetry[0],
        project_id=telemetry[1],
        ingest_token=telemetry[2],
        templates=_templates(args.routes),
        trust_forwarded_for=args.trust_forwarded_for,
    )
    host, _, port = args.listen.rpartition(":")
    log.info(
        "ari proxy %s -> %s controls=%s telemetry=%s",
        args.listen,
        args.upstream,
        bool(secret),
        all(telemetry),
    )
    uvicorn.run(
        app, host=host or "0.0.0.0", port=int(port), proxy_headers=False, server_header=False
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
