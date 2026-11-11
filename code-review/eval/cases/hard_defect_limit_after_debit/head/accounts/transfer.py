from accounts.ledger import Ledger
from accounts.limits import record


class InsufficientFunds(Exception):
    pass


def transfer(ledger: Ledger, src: str, dst: str, amount: int) -> None:
    if amount <= 0:
        raise ValueError("amount must be positive")
    if dst not in ledger.balances:
        raise KeyError(dst)
    if ledger.balances[src] < amount:
        raise InsufficientFunds(src)
    ledger.balances[src] -= amount
    record(ledger, src, amount)
    ledger.balances[dst] += amount
