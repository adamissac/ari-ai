"""Cart totals. A cart total is never negative (README)."""

from decimal import Decimal


def subtotal(prices: list[Decimal]) -> Decimal:
    return sum(prices, Decimal("0"))
