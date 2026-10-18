"""Refunds. Total refunds for a payment must never exceed the payment amount."""

from dataclasses import dataclass, field


class RefundTooLarge(Exception):
    pass


@dataclass
class Payment:
    amount_cents: int
    refunds: list[int] = field(default_factory=list)


def refund(payment: Payment, cents: int) -> None:
    if cents <= 0:
        raise ValueError("refund must be positive")
    if cents > payment.amount_cents:
        raise RefundTooLarge(cents)
    payment.refunds.append(cents)
