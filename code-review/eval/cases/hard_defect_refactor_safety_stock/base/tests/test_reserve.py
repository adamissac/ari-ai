import pytest
from inventory.reserve import Item, OutOfStock, report_line, reserve


def test_reserve_takes_units():
    item = Item("bolt", on_hand=10)
    reserve(item, 4)
    assert item.reserved == 4


def test_cannot_reserve_more_than_is_free():
    item = Item("bolt", on_hand=10, reserved=8)
    with pytest.raises(OutOfStock):
        reserve(item, 3)


def test_report_line():
    assert report_line(Item("bolt", on_hand=10, reserved=3)) == "bolt: 7 available"
