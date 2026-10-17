"""In-memory data layer for payments-lite. Synthetic fixture data only."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count


@dataclass(frozen=True)
class Customer:
    id: str
    name: str


@dataclass
class Payment:
    id: str
    customer_id: str
    amount_cents: int
    currency: str
    description: str

    def public(self) -> dict[str, object]:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "amount_cents": self.amount_cents,
            "currency": self.currency,
            "description": self.description,
        }


@dataclass
class Refund:
    id: str
    payment_id: str
    amount_cents: int
    reason: str

    def public(self) -> dict[str, object]:
        return {
            "id": self.id,
            "payment_id": self.payment_id,
            "amount_cents": self.amount_cents,
            "reason": self.reason,
        }


@dataclass
class PaymentStore:
    customers: dict[str, Customer] = field(default_factory=dict)
    tokens: dict[str, str] = field(default_factory=dict)  # token -> customer id
    payments: dict[str, Payment] = field(default_factory=dict)
    refunds: dict[str, Refund] = field(default_factory=dict)
    _refund_ids: count = field(default_factory=lambda: count(1))

    def customer_for_token(self, token: str) -> Customer | None:
        cid = self.tokens.get(token)
        return self.customers.get(cid) if cid else None

    def payments_for_customer(self, customer_id: str) -> list[Payment]:
        return [p for p in self.payments.values() if p.customer_id == customer_id]

    def get_payment(self, payment_id: str) -> Payment | None:
        return self.payments.get(payment_id)

    def get_payment_for_customer(self, payment_id: str, customer_id: str) -> Payment | None:
        payment = self.payments.get(payment_id)
        if payment is None or payment.customer_id != customer_id:
            return None
        return payment

    def refunds_for_payment(self, payment_id: str) -> list[Refund]:
        return [r for r in self.refunds.values() if r.payment_id == payment_id]

    def refunded_total(self, payment_id: str) -> int:
        return sum(r.amount_cents for r in self.refunds_for_payment(payment_id))

    def add_refund(self, payment_id: str, amount_cents: int, reason: str) -> Refund:
        refund = Refund(
            id=f"ref_{next(self._refund_ids):04d}",
            payment_id=payment_id,
            amount_cents=amount_cents,
            reason=reason,
        )
        self.refunds[refund.id] = refund
        return refund


# Synthetic fixture identities. These tokens are obviously fake and exist only
# inside the sandboxed target; they grant nothing anywhere else.
FIXTURE_TOKENS = {
    "fixture-token-alice": "cus_alice",
    "fixture-token-bob": "cus_bob",
}


def seed_store() -> PaymentStore:
    store = PaymentStore()
    store.customers["cus_alice"] = Customer(id="cus_alice", name="Alice Fixture")
    store.customers["cus_bob"] = Customer(id="cus_bob", name="Bob Fixture")
    store.tokens.update(FIXTURE_TOKENS)
    store.payments["pay_alice_1"] = Payment("pay_alice_1", "cus_alice", 5000, "usd", "Fixture order A-1")
    store.payments["pay_alice_2"] = Payment("pay_alice_2", "cus_alice", 1250, "usd", "Fixture order A-2")
    store.payments["pay_bob_1"] = Payment("pay_bob_1", "cus_bob", 9900, "usd", "Fixture order B-1")
    return store
