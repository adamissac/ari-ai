def split(total: int, people: int) -> list[int]:
    if people <= 0:
        raise ValueError("people must be positive")
    if total < 0:
        raise ValueError("total cannot be negative")
    share, extra = divmod(total, people)
    return [share + 1] * extra + [share] * (people - extra)
