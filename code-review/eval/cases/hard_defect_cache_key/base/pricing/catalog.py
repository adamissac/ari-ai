LIST_PRICES = {"widget": 1000, "gadget": 2500, "gizmo": 480}


def list_price(sku: str) -> int:
    return LIST_PRICES[sku]
