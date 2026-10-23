"""Versioned internal research provider; not a shared or network-facing API.

Capture under the owning lab's lock. Returned snapshots contain no credentials.
See docs/research/authorization-context/README.md for authority and clock limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol

from rl_defense.research.authorization import ReadContext, ReadGrant, authorize_read

if TYPE_CHECKING:
    from payments_lite.store import Store

AuthorizationClass = Literal["owner", "delegated", "unauthorized", "unknown"]
PROVIDER_VERSION = "0.1.0"


@dataclass(frozen=True)
class AuthorizationSnapshot:
    provider_version: str
    authority: str
    clock_domain: str
    revision: int
    context: ReadContext = field(repr=False)

    def classify(self, *, tick: int) -> AuthorizationClass:
        if (
            self.provider_version != PROVIDER_VERSION
            or not self.authority
            or not self.clock_domain
            or type(self.revision) is not int
            or self.revision < 0
        ):
            return "unknown"
        decision = authorize_read(self.context, now=tick)
        if decision.outcome == "abstain":
            return "unknown"
        if decision.outcome == "deny":
            return "unauthorized"
        return "owner" if self.context.principal == self.context.owner else "delegated"


class AuthorizationContextProvider(Protocol):
    """Credential/resource are lookup inputs, never permission assertions.

    tick is supplied by the trusted host clock. This internal protocol assumes
    the caller holds the authority lock across capture and read release.
    """

    def capture(self, *, credential: str, resource: str, tick: int) -> AuthorizationSnapshot: ...


class PaymentsLiteAuthorizationProvider:
    """Adapter over private trusted Store and existing lab-managed grants.

    No external writers, client grant parameters, network calls or ControlGrants.
    Construct/capture while holding PaymentReadLab's lock; do not retain this
    view across mutations. Snapshot contents are immutable copies of the facts.
    """

    def __init__(
        self,
        store: Store,
        grants: tuple[ReadGrant, ...] | None,
        *,
        clock_domain: str,
        revision: int,
    ) -> None:
        self._store = store
        self._grants = grants
        self._clock_domain = clock_domain
        self._revision = revision

    def capture(self, *, credential: str, resource: str, tick: int) -> AuthorizationSnapshot:
        if type(tick) is not int:
            raise ValueError("capture requires integer trusted clock ticks")
        principal = self._store.tokens.get(credential)
        customer = self._store.customers.get(principal)
        if customer is None or customer.id != principal:
            principal = None
        payment = self._store.payments.get(resource)
        owner = payment.customer_id if payment is not None else None
        owner_record = self._store.customers.get(owner)
        if owner_record is None or owner_record.id != owner:
            owner = None
        context = ReadContext(
            principal,
            owner,
            resource,
            self._grants,
            tick,
            tick + 5,
            contradictory=payment is not None and payment.id != resource,
        )
        return AuthorizationSnapshot(
            PROVIDER_VERSION,
            "payments-lite-owned-research",
            self._clock_domain,
            self._revision,
            context,
        )
