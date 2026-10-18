import pytest
from billing.invoices import Invoice, NotFound, get_invoice


def test_other_customer_cannot_read_invoice():
    store = {"inv1": Invoice("inv1", "alice", 100)}
    with pytest.raises(NotFound):
        get_invoice(store, "bob", "inv1")
