def split(total: int, people: int) -> list[int]:
    if people <= 0:
        raise ValueError("people must be positive")
    if total < 0:
        raise ValueError("total cannot be negative")
    shares = [total // people] * people
    for i in range(total % people):
        shares[i] += 1
    return shares
