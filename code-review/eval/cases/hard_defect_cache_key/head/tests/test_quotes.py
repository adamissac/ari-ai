import pytest
from pricing.quotes import clear_cache, quote


def test_standard_pays_list_price():
    assert quote("standard", "widget", 2) == 2000


def test_gold_gets_ten_percent_off():
    assert quote("gold", "gadget", 1) == 2250


def test_silver_gets_five_percent_off():
    assert quote("silver", "gizmo", 5) == 2280


def test_repeated_quote_is_stable():
    clear_cache()
    assert quote("gold", "gizmo", 2) == quote("gold", "gizmo", 2) == 864


def test_quantity_must_be_positive():
    with pytest.raises(ValueError):
        quote("standard", "widget", 0)
