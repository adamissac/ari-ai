FREE_SHIPPING_FROM = 5000
FLAT_FEE = 599
EXPRESS_FEE = 1499


def qualifies_for_free_shipping(subtotal_cents: int) -> bool:
    return subtotal_cents > FREE_SHIPPING_FROM


def shipping_fee(subtotal_cents: int, express: bool = False) -> int:
    if subtotal_cents < 0:
        raise ValueError("subtotal cannot be negative")
    if express:
        return EXPRESS_FEE
    return 0 if qualifies_for_free_shipping(subtotal_cents) else FLAT_FEE
