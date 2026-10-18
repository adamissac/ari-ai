from decimal import Decimal

from cart.totals import total_with_coupon


def test_big_coupon_makes_order_free_not_negative():
    assert total_with_coupon([Decimal("5.00")], Decimal("8.00")) == Decimal("0")
