from decimal import Decimal

from tests.conftest import ALICE, BOB


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_requires_token(client):
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_me(client):
    assert client.get("/me", headers=ALICE).json()["id"] == "cus_alice"


def test_customer_can_read_own_profile(client):
    assert client.get("/customers/cus_alice", headers=ALICE).status_code == 200


def test_customer_cannot_read_other_customer_profile(client):
    assert client.get("/customers/cus_bob", headers=ALICE).status_code == 404


def test_list_payments_only_returns_own(client):
    ids = {p["id"] for p in client.get("/payments", headers=ALICE).json()}
    assert ids == {"pay_a1", "pay_a2"}


def test_get_own_payment(client):
    r = client.get("/payments/pay_a1", headers=ALICE)
    assert r.status_code == 200
    assert Decimal(r.json()["amount"]) == Decimal("120.00")


def test_create_payment(client):
    r = client.post("/payments", headers=BOB, json={"amount": "9.99", "description": "Top-up"})
    assert r.status_code == 201
    assert r.json()["customer_id"] == "cus_bob"


def test_payment_amount_must_be_positive(client):
    assert client.post("/payments", headers=BOB, json={"amount": "0"}).status_code == 422


def test_partial_refund(client):
    r = client.post("/refunds", headers=ALICE, json={"payment_id": "pay_a1", "amount": "20.00"})
    assert r.status_code == 201
    pay = client.get("/payments/pay_a1", headers=ALICE).json()
    assert Decimal(pay["refunded"]) == Decimal("20.00")


def test_refund_larger_than_payment_rejected(client):
    r = client.post("/refunds", headers=ALICE, json={"payment_id": "pay_a2", "amount": "16.00"})
    assert r.status_code == 422


def test_cannot_refund_other_customers_payment(client):
    r = client.post("/refunds", headers=BOB, json={"payment_id": "pay_a1", "amount": "1.00"})
    assert r.status_code == 404


def test_refund_visible_only_to_owner(client):
    ref = client.post(
        "/refunds", headers=ALICE, json={"payment_id": "pay_a1", "amount": "5.00"}
    ).json()
    assert client.get(f"/refunds/{ref['id']}", headers=ALICE).status_code == 200
    assert client.get(f"/refunds/{ref['id']}", headers=BOB).status_code == 404
