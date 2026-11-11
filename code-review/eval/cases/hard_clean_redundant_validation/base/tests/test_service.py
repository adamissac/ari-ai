from orders.models import Order
from orders.service import add_line, total_units


def test_lines_add_up():
    order = Order()
    add_line(order, "a", 2)
    add_line(order, "b", 5)
    assert total_units(order) == 7
