from accounts.ledger import Ledger

DAILY_LIMIT = 100_000


class LimitExceeded(Exception):
    pass


def record(ledger: Ledger, account: str, amount: int) -> None:
    """Count `amount` against the account's daily total, or raise LimitExceeded."""
    total = ledger.sent_today.get(account, 0) + amount
    if total > DAILY_LIMIT:
        raise LimitExceeded(account)
    ledger.sent_today[account] = total
