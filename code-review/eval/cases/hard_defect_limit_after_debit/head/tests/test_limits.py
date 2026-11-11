import pytest
from accounts.ledger import Ledger
from accounts.limits import LimitExceeded
from accounts.transfer import transfer


def test_transfers_count_against_the_daily_total():
    ledger = Ledger({"a": 500_000, "b": 0})
    transfer(ledger, "a", "b", 60_000)
    assert ledger.sent_today == {"a": 60_000}


def test_over_the_limit_is_refused():
    ledger = Ledger({"a": 500_000, "b": 0})
    transfer(ledger, "a", "b", 60_000)
    with pytest.raises(LimitExceeded):
        transfer(ledger, "a", "b", 60_000)
    assert ledger.sent_today == {"a": 60_000}
