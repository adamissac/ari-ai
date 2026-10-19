"""A defensive gateway in front of the owned demo app.

Every request the traffic driver makes goes through :meth:`DefensiveGateway.request`.
The gateway enforces the currently-selected defensive controls **for real** (an
isolated node's requests are never forwarded; a rate-limited node drops a fraction),
forwards the rest to the real app over an in-process ASGI transport, and records the
true outcome of each request. Telemetry and reward are computed from these records,
not from any hidden state.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import httpx

with warnings.catch_warnings():
    # starlette advises httpx2; the sync TestClient on httpx works fine for the lab loop.
    warnings.simplefilter("ignore")
    from starlette.testclient import TestClient

from rl_defense.live.contracts import DefenseControls
from rl_defense.live.topology import RouteTopology


@dataclass
class RequestRecord:
    """The real outcome of one request through the gateway."""

    node: str
    method: str
    path: str
    actor: str  # customer id of the caller (or "anon")
    is_attack: bool  # the driver intended this as a cross-tenant / abusive request
    status: int  # HTTP status actually returned (gateway 503/429 or the app's own)
    blocked_reason: str | None  # "isolated" | "rate_limited" | None
    compromised: bool  # an attack request that really succeeded (cross-tenant 200)

    @property
    def allowed(self) -> bool:
        return self.blocked_reason is None


class DefensiveGateway:
    """Wraps the target ASGI app; enforces :class:`DefenseControls` per node."""

    def __init__(self, app, topology: RouteTopology, controls: DefenseControls) -> None:
        self._client = TestClient(app, raise_server_exceptions=False)
        self._topology = topology
        self.controls = controls
        self.records: list[RequestRecord] = []
        self._rl_counter: dict[str, int] = {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> DefensiveGateway:
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        self.close()

    def clear_records(self) -> None:
        self.records = []

    def request(
        self,
        method: str,
        path: str,
        *,
        actor: str = "anon",
        token: str | None = None,
        is_attack: bool = False,
    ) -> RequestRecord:
        node = self._topology.node_for(method, path)
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        # --- enforcement happens before anything reaches the app ---
        if self.controls.isolated.get(node, False):
            rec = RequestRecord(node, method, path, actor, is_attack, 503, "isolated", False)
            self.records.append(rec)
            return rec
        if self.controls.rate_limited.get(node, False):
            n = self._rl_counter.get(node, 0)
            self._rl_counter[node] = n + 1
            every = max(1, self.controls.rate_limit_allow_every)
            if n % every != 0:  # only 1 of every `every` requests passes
                rec = RequestRecord(node, method, path, actor, is_attack, 429, "rate_limited", False)
                self.records.append(rec)
                return rec

        # --- forward to the real app ---
        resp = self._client.request(method, path, headers=headers)
        compromised = self._is_compromise(is_attack, actor, resp)
        rec = RequestRecord(node, method, path, actor, is_attack, resp.status_code, None, compromised)
        self.records.append(rec)
        return rec

    @staticmethod
    def _is_compromise(is_attack: bool, actor: str, resp: httpx.Response) -> bool:
        """A real cross-tenant read: an attack request that returned 200 with another
        customer's data. Verified against the response body, not assumed."""
        if not is_attack or resp.status_code != 200:
            return False
        try:
            body = resp.json()
        except ValueError:
            return False
        owner = body.get("customer_id") if isinstance(body, dict) else None
        return owner is not None and owner != actor
