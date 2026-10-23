"""Opt-in owned payments-lite read wrapper; no serving, gateway or RL registration.

This fixture owns a private store. Trusted mutations and requests serialize under
one lock; do not use this wrapper around an application with outside writers.
"""

from __future__ import annotations

import asyncio
import copy
import re
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from rl_defense.research.authorization import ReadContext, ReadGrant, authorize_read

if TYPE_CHECKING:
    from payments_lite.store import Store

_PAYMENT_READ = re.compile(r"^/payments/([A-Za-z0-9_-]+)$")


class _ResponseBudgetExceeded(RuntimeError):
    pass


class PaymentReadLab:
    """Read-only ASGI surface over the actual deliberately vulnerable example app."""

    def __init__(
        self,
        store: Store,
        *,
        grants: tuple[ReadGrant, ...] | None,
        clock: Callable[[], int] = lambda: time.monotonic_ns() // 1_000_000_000,
        response_timeout_s: float = 5,
    ) -> None:
        from payments_lite.app import create_app

        if type(response_timeout_s) not in (int, float) or not 0 < response_timeout_s <= 5:
            raise ValueError("fixture timeout must be positive and at most five seconds")
        self._response_timeout_s = response_timeout_s
        self._store = copy.deepcopy(store)
        self._app: ASGIApp = create_app(self._store)
        self._grants = grants
        self._clock = clock
        self._lock = asyncio.Lock()
        self.forwarded = 0

    async def replace_grants(self, grants: tuple[ReadGrant, ...] | None) -> None:
        async with self._lock:
            self._grants = grants

    async def bind_token(self, token: str, principal: str | None) -> None:
        async with self._lock:
            if principal is None:
                self._store.tokens.pop(token, None)
            else:
                if principal not in self._store.customers:
                    raise ValueError("unknown fixture principal")
                self._store.tokens[token] = principal

    async def transfer_payment(self, resource: str, owner: str) -> None:
        async with self._lock:
            if owner not in self._store.customers:
                raise ValueError("unknown fixture owner")
            self._store.payments[resource].customer_id = owner

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        match = _PAYMENT_READ.fullmatch(scope["path"])
        # Avoid path-decoding ambiguity; this research surface exposes reads only.
        if (
            scope["method"] != "GET"
            or match is None
            or scope.get("raw_path", scope["path"].encode()) != scope["path"].encode()
        ):
            await JSONResponse({}, status_code=404)(scope, receive, send)
            return
        authorization = [v for k, v in scope["headers"] if k.lower() == b"authorization"]
        if len(authorization) != 1 or not authorization[0].startswith(b"Bearer "):
            await JSONResponse({}, status_code=503)(scope, receive, send)
            return
        try:
            token = authorization[0][7:].decode("ascii")
        except UnicodeDecodeError:
            await JSONResponse({}, status_code=503)(scope, receive, send)
            return
        async with self._lock:
            now = self._clock()
            principal = self._store.tokens.get(token)
            if principal not in self._store.customers:
                principal = None
            resource = match.group(1)
            payment = self._store.payments.get(resource)
            owner = payment.customer_id if payment is not None else None
            if owner not in self._store.customers:
                owner = None
            context = ReadContext(
                principal,
                owner,
                resource,
                self._grants,
                now,
                now + 5,
                contradictory=payment is not None and payment.id != resource,
            )
            decision = authorize_read(context, now=now)
            if decision.outcome != "allow":
                await JSONResponse({}, status_code=404 if decision.outcome == "deny" else 503)(
                    scope, receive, send
                )
                return
            messages: list[Message] = []
            size = 0

            async def capture(message: Message) -> None:
                nonlocal size
                size += len(message.get("body", b""))
                if size > 65536:
                    raise _ResponseBudgetExceeded("owned fixture response budget exceeded")
                messages.append(message)

            self.forwarded += 1
            try:
                await asyncio.wait_for(
                    self._app(scope, receive, capture), timeout=self._response_timeout_s
                )
            except (TimeoutError, _ResponseBudgetExceeded):
                await JSONResponse({}, status_code=503)(scope, receive, send)
                return
            # Buffering prevents a mid-request expiry from leaking an already-started body.
            if authorize_read(context, now=self._clock()).outcome != "allow":
                await JSONResponse({}, status_code=503)(scope, receive, send)
                return
            for message in messages:
                await send(message)
