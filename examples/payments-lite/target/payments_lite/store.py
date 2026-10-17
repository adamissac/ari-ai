"""In-memory data store seeded with synthetic fixture data. Reset per app instance."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Customer:
    id: str
    name: str
    email: str


@dataclass
class Payment:
    id: str
    customer_id: str
    amount: Decimal
    currency: str
    description: str


@dataclass
class Refund:
    id: str
    payment_id: str
    customer_id: str
    amount: Decimal
    reason: str


@dataclass
class Store:
    customers: dict[str, Customer] = field(default_factory=dict)
    payments: dict[str, Payment] = field(default_factory=dict)
    refunds: dict[str, Refund] = field(default_factory=dict)
    tokens: dict[str, str] = field(default_factory=dict)  # bearer token -> customer id
    _counter: int = 0

    def next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter:04d}"

    def refunds_for(self, payment_id: str) -> list[Refund]:
        return [r for r in self.refunds.values() if r.payment_id == payment_id]


def seeded_store() -> Store:
    """Two synthetic customers with obviously fake tokens (fixture data, not secrets)."""
    s = Store()
    s.customers = {
        "cus_alice": Customer("cus_alice", "Alice Example", "alice@example.test"),
        "cus_bob": Customer("cus_bob", "Bob Example", "bob@example.test"),
    }
    s.tokens = {"fixture-token-alice": "cus_alice", "fixture-token-bob": "cus_bob"}
    s.payments = {
        "pay_a1": Payment("pay_a1", "cus_alice", Decimal("120.00"), "USD", "Annual plan"),
        "pay_a2": Payment("pay_a2", "cus_alice", Decimal("15.50"), "USD", "Add-on"),
        "pay_b1": Payment("pay_b1", "cus_bob", Decimal("80.00"), "USD", "Monthly plan"),
    }
    return s
