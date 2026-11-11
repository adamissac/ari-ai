import pytest
from pricing.quotes import quote


def test_standard_pays_list_price():
    assert quote("standard", "widget", 2) == 2000


def test_gold_gets_ten_percent_off():
    assert quote("gold", "gadget", 1) == 2250


def test_quantity_must_be_positive():
    with pytest.raises(ValueError):
        quote("standard", "widget", 0)
