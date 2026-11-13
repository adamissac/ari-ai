"""ASGI middleware that reports per-route counters to Ari's runtime ingest.

Runs inside the monitored application. Standard library only, so the file can be copied
into an app that does not install this package.

It sends counts and nothing else: route template, requests, 4xx, 5xx, 401/403. It never
reads or sends a raw path, query string, header, body or client address. A request the
framework did not match to a route template is counted under ``/__unmatched__``.

It does not report per-principal ownership counters, so Ari's rules run on these windows
but the RL policy abstains (it requires verified ownership context).

    app.add_middleware(
        AriCollector,
        api_base="https://<ari-api-host>",
        project_id="prj_...",
        token=os.environ["ARI_INGEST_TOKEN"],   # application-bound ingest token
    )
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from collections.abc import Awaitable, Callable, MutableMapping
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger("ari.collector")

Scope = MutableMapping[str, Any]
Sender = Callable[[dict[str, Any]], None]

METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
UNMATCHED = "/__unmatched__"
OVERFLOW = "/__overflow__"
MAX_ROUTES = 400  # ingest accepts 500 per batch; leave room for per-method overflow rows
MIN_WINDOW_S = 5.0  # ingest allows 60 batches a minute per token
MAX_WINDOW_S = 3600.0


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).isoformat()


def route_template(scope: Scope) -> str:
    """The framework's route template, never the raw path."""
    path = getattr(scope.get("route"), "path", None)
    if not isinstance(path, str) or not path.startswith("/") or any(c.isspace() for c in path):
        return UNMATCHED
    return path[:300]


class AriCollector:
    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        *,
        api_base: str = "",
        project_id: str = "",
        token: str = "",
        window_s: float = 60.0,
        source: str = "owned_staging",
        send: Sender | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.app = app
        self.window_s = min(MAX_WINDOW_S, max(MIN_WINDOW_S, window_s))
        self.source = source
        self._url = f"{api_base.rstrip('/')}/api/v1/ingest/runtime/{project_id}"
        self._token = token
        self._send = send or self._post
        self._clock = clock
        self._lock = threading.Lock()
        self._counts: dict[str, list[int]] = {}
        self._start = clock()

    async def __call__(self, scope: Scope, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        status = 500  # an exception before the response starts is a server error

        async def capture(message: MutableMapping[str, Any]) -> None:
            nonlocal status
            if message.get("type") == "http.response.start":
                status = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            self._record(str(scope.get("method", "")).upper(), route_template(scope), status)

    def _record(self, method: str, template: str, status: int) -> None:
        if method not in METHODS:
            return
        key = f"{method} {template}"
        batch = None
        with self._lock:
            if key not in self._counts and len(self._counts) >= MAX_ROUTES:
                key = f"{method} {OVERFLOW}"
            row = self._counts.setdefault(key, [0, 0, 0, 0])
            row[0] += 1
            row[1] += 400 <= status < 500
            row[2] += status >= 500
            row[3] += status in (401, 403)
            now = self._clock()
            if now - self._start >= self.window_s:
                batch = self._take(now)
        if batch is not None:
            threading.Thread(target=self._safe_send, args=(batch,), daemon=True).start()

    def _take(self, now: float) -> dict[str, Any]:
        """Caller holds the lock. A long idle gap is clamped to the ingest maximum."""
        start = max(self._start, now - MAX_WINDOW_S)
        counts, self._counts, self._start = self._counts, {}, now
        return {
            "source": self.source,
            "window_start": _iso(start),
            "window_end": _iso(now),
            "routes": [
                {
                    "route": route,
                    "requests": n,
                    "status_4xx": e4,
                    "status_5xx": e5,
                    "auth_failures": auth,
                }
                for route, (n, e4, e5, auth) in sorted(counts.items())
            ],
        }

    def flush(self) -> None:
        """Send the open window now (call at shutdown). No-op when nothing was counted."""
        with self._lock:
            now = self._clock()
            if not self._counts or now - self._start < 1:
                return
            batch = self._take(now)
        self._safe_send(batch)

    def _safe_send(self, batch: dict[str, Any]) -> None:
        # Telemetry must never break or slow the application: a failed window is dropped.
        try:
            self._send(batch)
        except Exception as exc:  # noqa: BLE001
            log.warning("ari collector: window dropped (%s)", type(exc).__name__)

    def _post(self, batch: dict[str, Any]) -> None:
        request = urllib.request.Request(  # noqa: S310 — operator-configured https URL
            self._url,
            data=json.dumps(batch).encode(),
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            response.read()
