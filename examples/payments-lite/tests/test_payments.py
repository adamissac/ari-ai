"""Existing payments-lite suite. Passes, but is deliberately incomplete."""

from tests.conftest import ALICE, BOB


def test_health_is_public(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_payments_require_authentication(client):
    assert client.get("/payments").status_code == 401
    assert client.get("/payments/pay_alice_1").status_code == 401


def test_customer_lists_only_own_payments(client):
    ids = {p["id"] for p in client.get("/payments", headers=ALICE).json()}
    assert ids == {"pay_alice_1", "pay_alice_2"}


def test_owner_can_read_own_payment(client):
    resp = client.get("/payments/pay_alice_1", headers=ALICE)
    assert resp.status_code == 200
    assert resp.json()["amount_cents"] == 5000


def test_unknown_payment_is_404(client):
    assert client.get("/payments/pay_nope", headers=ALICE).status_code == 404


def test_refund_list_of_other_customers_payment_is_404(client):
    # Tenant isolation: a customer must never see another customer's payment data.
    assert client.get("/payments/pay_bob_1/refunds", headers=ALICE).status_code == 404


def test_partial_refund(client):
    resp = client.post("/payments/pay_alice_1/refunds", json={"amount_cents": 1000}, headers=ALICE)
    assert resp.status_code == 201
    refunds = client.get("/payments/pay_alice_1/refunds", headers=ALICE).json()
    assert [r["amount_cents"] for r in refunds] == [1000]


def test_cannot_refund_other_customers_payment(client):
    resp = client.post("/payments/pay_alice_1/refunds", json={"amount_cents": 100}, headers=BOB)
    assert resp.status_code == 404
