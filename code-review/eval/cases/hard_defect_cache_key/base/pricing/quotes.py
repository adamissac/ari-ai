from pricing.catalog import list_price
from pricing.tiers import discount_percent


def unit_price(tier: str, sku: str) -> int:
    return list_price(sku) * (100 - discount_percent(tier)) // 100


def quote(tier: str, sku: str, qty: int) -> int:
    if qty <= 0:
        raise ValueError("qty must be positive")
    return unit_price(tier, sku) * qty
