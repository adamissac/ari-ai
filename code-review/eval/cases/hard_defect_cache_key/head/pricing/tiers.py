DISCOUNTS = {"standard": 0, "silver": 5, "gold": 10}


def discount_percent(tier: str) -> int:
    return DISCOUNTS[tier]
