DISCOUNTS = {"standard": 0, "gold": 10}


def discount_percent(tier: str) -> int:
    return DISCOUNTS[tier]
