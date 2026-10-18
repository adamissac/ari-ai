from decimal import ROUND_HALF_EVEN, Decimal

CENT = Decimal("0.01")


def sales_tax(subtotal: Decimal, rate: Decimal) -> Decimal:
    """Tax owed on ``subtotal`` at ``rate`` (e.g. Decimal("0.05")), rounded to cents."""
    return (subtotal * rate).quantize(CENT, rounding=ROUND_HALF_EVEN)
