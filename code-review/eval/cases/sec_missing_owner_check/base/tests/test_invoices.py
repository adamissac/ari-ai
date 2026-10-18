from billing.invoices import Invoice, get_invoice


def test_owner_reads_invoice():
    store = {"inv1": Invoice("inv1", "alice", 100)}
    assert get_invoice(store, "alice", "inv1").total_cents == 100
