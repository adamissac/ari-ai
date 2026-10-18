from decimal import Decimal

from cart.totals import subtotal


def test_subtotal():
    assert subtotal([Decimal("1.00"), Decimal("2.50")]) == Decimal("3.50")
