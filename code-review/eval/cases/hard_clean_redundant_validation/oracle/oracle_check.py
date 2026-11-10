import pytest
from orders.models import InvalidQuantity, Order
from orders.service import add_line


@pytest.mark.parametrize("qty", [0, -3, 1000])
def test_invalid_quantity_is_rejected_and_the_order_is_unchanged(qty):
    order = Order()
    with pytest.raises(InvalidQuantity):
        add_line(order, "a", qty)
    assert order.lines == []


@pytest.mark.parametrize("qty", [1, 999])
def test_bounds_are_accepted(qty):
    assert add_line(Order(), "a", qty).qty == qty
