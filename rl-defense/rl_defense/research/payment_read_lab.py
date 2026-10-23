"""Opt-in owned payments-lite read wrapper; no serving, gateway or RL registration.

This fixture owns a private store. Trusted mutations and requests serialize under
one lock; do not use this wrapper around an application with outside writers.
"""

from __future__ import annotations

import asyncio
import copy
import json
import re
import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from rl_defense.research.authorization import ReadGrant
from rl_defense.research.authorization_provider import PaymentsLiteAuthorizationProvider

if TYPE_CHECKING:
    from payments_lite.store import Store

_PAYMENT_READ = re.compile(r"^/payments/([A-Za-z0-9_-]+)$")


class _ResponseBudgetExceeded(RuntimeError):
    pass


class _ResponseIntegrityError(RuntimeError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate response JSON key")
        result[key] = value
    return result


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
        self._clock_domain = f"payments-lite:{uuid.uuid4()}"
        self._revision = 0
        self.forwarded = 0

    async def replace_grants(self, grants: tuple[ReadGrant, ...] | None) -> None:
        async with self._lock:
            self._grants = grants
            self._revision += 1

    async def bind_token(self, token: str, principal: str | None) -> None:
        async with self._lock:
            if principal is None:
                self._store.tokens.pop(token, None)
            else:
                if principal not in self._store.customers:
                    raise ValueError("unknown fixture principal")
                self._store.tokens[token] = principal
            self._revision += 1

    async def transfer_payment(self, resource: str, owner: str) -> None:
        async with self._lock:
            if owner not in self._store.customers:
                raise ValueError("unknown fixture owner")
            self._store.payments[resource].customer_id = owner
            self._revision += 1

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
            provider = PaymentsLiteAuthorizationProvider(
                self._store,
                self._grants,
                clock_domain=self._clock_domain,
                revision=self._revision,
            )
            snapshot = provider.capture(credential=token, resource=match.group(1), tick=now)
            context = snapshot.context
            classification = snapshot.classify(tick=now)
            if classification not in ("owner", "delegated"):
                await JSONResponse(
                    {}, status_code=404 if classification == "unauthorized" else 503
                )(scope, receive, send)
                return
            messages: list[Message] = []
            size = 0

            async def capture(message: Message) -> None:
                nonlocal size
                body_bytes = message.get("body", b"")
                if type(body_bytes) is not bytes:
                    raise _ResponseIntegrityError("response body must be bytes")
                size += len(body_bytes)
                if size > 65536 or len(messages) >= 1024:
                    raise _ResponseBudgetExceeded("owned fixture response budget exceeded")
                messages.append(message)

            self.forwarded += 1
            try:
                await asyncio.wait_for(
                    self._app(scope, receive, capture), timeout=self._response_timeout_s
                )
            except (TimeoutError, _ResponseBudgetExceeded, _ResponseIntegrityError):
                await JSONResponse({}, status_code=503)(scope, receive, send)
                return
            # Buffering prevents a mid-request expiry from leaking an already-started body.
            if snapshot.classify(tick=self._clock()) not in ("owner", "delegated"):
                await JSONResponse({}, status_code=503)(scope, receive, send)
                return
            # Validate the existing example response contract before releasing any
            # downstream body or headers. A valid request cannot bless a wrong object.
            from payments_lite.app import PaymentOut

            try:
                if not messages or messages[0].get("type") != "http.response.start":
                    raise _ResponseIntegrityError("missing response start")
                if messages[0].get("status") != 200:
                    raise _ResponseIntegrityError("downstream read did not succeed")
                bodies = messages[1:]
                if not bodies or any(m.get("type") != "http.response.body" for m in bodies):
                    raise _ResponseIntegrityError("invalid response sequence")
                if any(not m.get("more_body", False) for m in bodies[:-1]) or bodies[-1].get(
                    "more_body", False
                ):
                    raise _ResponseIntegrityError("incomplete or repeated response body")
                body = b"".join(m.get("body", b"") for m in bodies)
                raw = json.loads(body, object_pairs_hook=_unique_object)
                if not isinstance(raw, dict) or set(raw) != set(PaymentOut.model_fields):
                    raise _ResponseIntegrityError("unexpected payment response fields")
                payment_response = PaymentOut.model_validate_json(body, strict=True)
                if (
                    payment_response.id != context.resource
                    or payment_response.customer_id != context.owner
                ):
                    raise _ResponseIntegrityError("response does not match authorized resource")
            except (ValueError, _ResponseIntegrityError):
                await JSONResponse({}, status_code=503)(scope, receive, send)
                return
            # Construct fresh headers from validated data, dropping cookies, redirects
            # and other unexpected downstream header values.
            response = JSONResponse(payment_response.model_dump(mode="json"))
            if snapshot.classify(tick=self._clock()) not in ("owner", "delegated"):
                await JSONResponse({}, status_code=503)(scope, receive, send)
                return
            await response(scope, receive, send)
