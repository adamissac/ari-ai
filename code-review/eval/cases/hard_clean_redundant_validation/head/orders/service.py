from orders.models import Line, Order


def add_line(order: Order, sku: str, qty: int) -> Line:
    line = Line(sku, qty)
    order.lines.append(line)
    return line


def total_units(order: Order) -> int:
    return sum(line.qty for line in order.lines)
