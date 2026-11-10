import pytest
from accounts.ledger import Ledger
from accounts.limits import LimitExceeded
from accounts.transfer import transfer


def test_a_transfer_refused_by_the_limit_moves_no_money():
    ledger = Ledger({"a": 500_000, "b": 0})
    with pytest.raises(LimitExceeded):
        transfer(ledger, "a", "b", 150_000)
    assert ledger.balances == {"a": 500_000, "b": 0}
