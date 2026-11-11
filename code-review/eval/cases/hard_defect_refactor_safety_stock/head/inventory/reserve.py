from dataclasses import dataclass

from inventory.levels import available


class OutOfStock(Exception):
    pass


@dataclass
class Item:
    sku: str
    on_hand: int
    reserved: int = 0
    safety_stock: int = 0


def reserve(item: Item, qty: int) -> None:
    if qty <= 0:
        raise ValueError("qty must be positive")
    if qty > available(item):
        raise OutOfStock(item.sku)
    item.reserved += qty


def report_line(item: Item) -> str:
    return f"{item.sku}: {available(item)} available"
