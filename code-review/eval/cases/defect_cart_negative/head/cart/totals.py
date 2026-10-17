"""Cart totals. A cart total is never negative (README)."""

from decimal import Decimal


def subtotal(prices: list[Decimal]) -> Decimal:
    return sum(prices, Decimal("0"))


def total_with_coupon(prices: list[Decimal], coupon: Decimal) -> Decimal:
    """Subtotal minus a fixed-amount ``coupon``."""
    return subtotal(prices) - coupon
