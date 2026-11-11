import pytest
from inventory.reserve import Item, OutOfStock, reserve


def test_safety_stock_is_never_promised():
    item = Item("bolt", on_hand=10, safety_stock=4)
    with pytest.raises(OutOfStock):
        reserve(item, 7)
