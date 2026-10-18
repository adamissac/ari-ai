from decimal import Decimal

from tax.calc import sales_tax


def test_half_cent_rounds_up():
    # 0.50 * 0.05 = 0.025 -> 0.03 under ROUND_HALF_UP
    assert sales_tax(Decimal("0.50"), Decimal("0.05")) == Decimal("0.03")
