"""Paging over an in-memory product list (see README paging rules)."""


def page(items: list[str], number: int, per_page: int = 10) -> list[str]:
    if number < 1 or per_page < 1:
        raise ValueError("page number and size start at 1")
    start = (number - 1) * per_page
    return items[start : start + per_page]
