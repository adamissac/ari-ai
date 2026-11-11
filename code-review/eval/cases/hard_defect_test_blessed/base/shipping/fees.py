FREE_SHIPPING_FROM = 5000
FLAT_FEE = 599


def shipping_fee(subtotal_cents: int) -> int:
    if subtotal_cents < 0:
        raise ValueError("subtotal cannot be negative")
    if subtotal_cents >= FREE_SHIPPING_FROM:
        return 0
    return FLAT_FEE
