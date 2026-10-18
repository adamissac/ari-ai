from decimal import Decimal

from tax.calc import CENT, sales_tax


def test_cent():
    assert str(CENT) == "0.01"


def test_simple_tax():
    assert sales_tax(Decimal("10.00"), Decimal("0.05")) == Decimal("0.50")
