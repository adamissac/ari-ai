"""A defensive gateway in front of the owned demo app.

Every request the traffic driver makes goes through :meth:`DefensiveGateway.request`.
The gateway enforces the currently-selected defensive controls **for real** (an
isolated node's requests are never forwarded; a rate-limited node drops a fraction; a
blocked principal's requests to the node it was blocked on get 403, whichever token it
presents),
forwards the rest to the real app over an in-process ASGI transport, and records the
true outcome of each request. Telemetry and reward are computed from these records,
not from any hidden state.

Detection uses only what the operator's own instrumentation can see: who the bearer
token belongs to and who owns the object being requested (read from the app's own
store). The traffic generator's ``is_attack`` label is kept on each record for
*metrics only* and never feeds telemetry.

v4: the instrumentation may also be given the business's delegation grants
(``grants``: delegate principal -> owners whose objects it may read). That is the
operator's own authorization data, so a read covered by a grant is not a cross-tenant
attempt. Without grants (the v1-v3 default) every foreign-owner read is flagged.
"""

from __future__ import annotations

import re
import warnings
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol

import httpx

with warnings.catch_warnings():
    # starlette advises httpx2; the sync TestClient on httpx works fine for the lab loop.
    warnings.simplefilter("ignore")
    from starlette.testclient import TestClient

from rl_defense.live.contracts import DefenseControls
from rl_defense.live.topology import RouteTopology


class Instrumentation(Protocol):
    """Operator-side knowledge of the app: principals and object ownership."""

    def principal(self, token: str | None) -> str | None: ...

    def resource_owner(self, method: str, path: str) -> str | None: ...

    def is_authorized_delegate(self, principal: str, owner: str) -> bool: ...


class PaymentsLiteInstrumentation:
    """Reads the owned demo app's own store (tokens, payments, customers)."""

    _PAYMENT = re.compile(r"^/payments/([^/]+)$")
    _CUSTOMER = re.compile(r"^/customers/([^/]+)$")

    def __init__(self, app, grants: Mapping[str, Iterable[str]] | None = None) -> None:  # noqa: ANN001
        self._store = app.state.store
        self._grants = {d: frozenset(o) for d, o in (grants or {}).items()}

    def is_authorized_delegate(self, principal: str, owner: str) -> bool:
        """True when the business granted ``principal`` read access to ``owner``'s data."""
        return owner in self._grants.get(principal, ())

    def principal(self, token: str | None) -> str | None:
        return self._store.tokens.get(token) if token else None

    def resource_owner(self, method: str, path: str) -> str | None:
        if m := self._PAYMENT.match(path):
            p = self._store.payments.get(m.group(1))
            return p.customer_id if p else None
        if m := self._CUSTOMER.match(path):
            return m.group(1) if m.group(1) in self._store.customers else None
        return None


@dataclass
class RequestRecord:
    """The real outcome of one request through the gateway."""

    node: str
    method: str
    path: str
    actor: str  # customer id of the caller (or "anon")
    is_attack: bool  # generator's label — METRICS ONLY, never used for telemetry
    status: int  # HTTP status actually returned (gateway 503/429 or the app's own)
    blocked_reason: str | None  # "isolated" | "principal_blocked" | "rate_limited" | None
    compromised: bool  # really succeeded cross-tenant read (allowed, 200, foreign owner in body)
    # detector: token's principal != object owner (and, v4, no delegation grant covers it)
    cross_tenant_attempt: bool = False
    principal: str | None = None  # whom the bearer token belongs to (operator-visible)
    owner: str | None = None  # who owns the requested object (operator-visible), if any

    @property
    def allowed(self) -> bool:
        return self.blocked_reason is None


class DefensiveGateway:
    """Wraps the target ASGI app; enforces :class:`DefenseControls` per node."""

    def __init__(
        self,
        app,  # noqa: ANN001
        topology: RouteTopology,
        controls: DefenseControls,
        instrumentation: Instrumentation | None = None,
        *,
        grants: Mapping[str, Iterable[str]] | None = None,
    ) -> None:
        if instrumentation is not None and grants is not None:
            raise ValueError("pass grants to the instrumentation, not to both")
        self._client = TestClient(app, raise_server_exceptions=False)
        self._topology = topology
        self._inst = instrumentation or PaymentsLiteInstrumentation(app, grants)
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
        principal = self._inst.principal(token)
        owner = self._inst.resource_owner(method, path)
        cross = (
            principal is not None
            and owner is not None
            and owner != principal
            and not self._inst.is_authorized_delegate(principal, owner)
        )

        def blocked(status: int, reason: str) -> RequestRecord:
            rec = RequestRecord(
                node, method, path, actor, is_attack, status, reason, False, cross, principal, owner
            )
            self.records.append(rec)
            return rec

        # --- enforcement happens before anything reaches the app ---
        if self.controls.isolated.get(node, False):
            return blocked(503, "isolated")
        if principal is not None and node in self.controls.blocked_principals.get(principal, ()):
            return blocked(403, "principal_blocked")
        if self.controls.rate_limited.get(node, False):
            n = self._rl_counter.get(node, 0)
            self._rl_counter[node] = n + 1
            every = max(1, self.controls.rate_limit_allow_every)
            if n % every != 0:  # only 1 of every `every` requests passes
                return blocked(429, "rate_limited")

        # --- forward to the real app ---
        resp = self._client.request(method, path, headers=headers)
        compromised = self._is_compromise(principal, resp)
        rec = RequestRecord(
            node,
            method,
            path,
            actor,
            is_attack,
            resp.status_code,
            None,
            compromised,
            cross,
            principal,
            owner,
        )
        self.records.append(rec)
        return rec

    def flagged_principals(self) -> dict[str, set[str]]:
        """Principals the instrumentation saw attempting cross-tenant access in the current
        records, with the nodes they did it on. Detector output only (no generator label)."""
        out: dict[str, set[str]] = {}
        for r in self.records:
            if r.cross_tenant_attempt and r.principal is not None:
                out.setdefault(r.principal, set()).add(r.node)
        return out

    @staticmethod
    def _is_compromise(principal: str | None, resp: httpx.Response) -> bool:
        """A real cross-tenant read: a 200 whose body belongs to someone other than the
        caller. Verified against the response body, not assumed from any label."""
        if principal is None or resp.status_code != 200:
            return False
        try:
            body = resp.json()
        except ValueError:
            return False
        owner = body.get("customer_id") if isinstance(body, dict) else None
        return owner is not None and owner != principal
