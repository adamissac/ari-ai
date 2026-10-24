"""Intended-behavior tests for inventory-lite."""

from fastapi.testclient import TestClient

from inventory_lite.app import create_app

client = TestClient(create_app())
ALICE = {"Authorization": "Bearer fixture-token-alice"}
BOB = {"Authorization": "Bearer fixture-token-bob"}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_requires_token():
    assert client.get("/items", headers={}).status_code == 401


def test_me():
    r = client.get("/me", headers=ALICE)
    assert r.status_code == 200 and r.json()["id"] == "wsp_alice"


def test_owner_reads_own_item():
    r = client.get("/items/item_a1", headers=ALICE)
    assert r.status_code == 200 and r.json()["sku"] == "SKU-100"


def test_warehouse_detail_requires_ownership():
    assert client.get("/warehouses/wsp_alice", headers=BOB).status_code == 404


def test_transfer_requires_ownership():
    r = client.post("/transfers", json={"item_id": "item_a1", "quantity": 1}, headers=BOB)
    assert r.status_code == 404


def test_transfer_capped_by_stock():
    r = client.post("/transfers", json={"item_id": "item_a1", "quantity": 999}, headers=ALICE)
    assert r.status_code == 422


def test_lists_only_own_items():
    r = client.get("/items", headers=BOB)
    assert r.status_code == 200
    assert {it["id"] for it in r.json()} == {"item_b1"}
