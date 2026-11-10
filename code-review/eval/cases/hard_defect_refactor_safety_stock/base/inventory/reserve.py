from dataclasses import dataclass


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
    free = max(item.on_hand - item.reserved - item.safety_stock, 0)
    if qty > free:
        raise OutOfStock(item.sku)
    item.reserved += qty


def report_line(item: Item) -> str:
    free = max(item.on_hand - item.reserved - item.safety_stock, 0)
    return f"{item.sku}: {free} available"
