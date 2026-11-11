from orders.models import MAX_QTY, InvalidQuantity, Line, Order


def add_line(order: Order, sku: str, qty: int) -> Line:
    if qty < 1 or qty > MAX_QTY:
        raise InvalidQuantity(qty)
    line = Line(sku, qty)
    order.lines.append(line)
    return line


def total_units(order: Order) -> int:
    return sum(line.qty for line in order.lines)
