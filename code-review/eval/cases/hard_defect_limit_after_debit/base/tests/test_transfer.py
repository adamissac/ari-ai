import pytest
from accounts.ledger import Ledger
from accounts.transfer import InsufficientFunds, transfer


def test_transfer_moves_money():
    ledger = Ledger({"a": 5000, "b": 0})
    transfer(ledger, "a", "b", 1200)
    assert ledger.balances == {"a": 3800, "b": 1200}


def test_insufficient_funds_changes_nothing():
    ledger = Ledger({"a": 100, "b": 0})
    with pytest.raises(InsufficientFunds):
        transfer(ledger, "a", "b", 500)
    assert ledger.balances == {"a": 100, "b": 0}
