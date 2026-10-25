"""Prove the planted defect in target/ exists and the negatives are really safe.

If one of these fails, someone fixed a planted defect or broke a lookalike, and the
demo/evaluation labels no longer match the target. Run from examples/inventory-lite:
    target/.venv/bin/python -m pytest -q label_checks
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "target"))
from inventory_lite.app import create_app  # noqa: E402

LABELS = yaml.safe_load((ROOT / "labels.yaml").read_text())
ALICE = {"Authorization": "Bearer fixture-token-alice"}
BOB = {"Authorization": "Bearer fixture-token-bob"}


@pytest.fixture
def client():
    return TestClient(create_app())


def test_labels_reference_real_symbols():
    src = (ROOT / "target/inventory_lite/app.py").read_text()
    for f in LABELS["planted_findings"]:
        assert f"def {f['root_cause_span']['symbol']}(" in src
    assert {f["id"] for f in LABELS["planted_findings"]} == {"fnd_planted_item_owner"}


def test_target_contains_no_answer_hints():
    for p in (ROOT / "target").rglob("*"):
        if p.is_file() and ".venv" not in p.parts and p.suffix in {".py", ".md", ".toml", ""}:
            text = p.read_text(errors="ignore").lower()
            assert "planted" not in text and "labels.yaml" not in text, p


def test_planted_item_owner_exists(client):
    """exp_workspace_items_owner_only is violated: another workspace's item is readable."""
    assert client.get("/items/item_b1", headers=ALICE).status_code == 200
    assert client.get("/items/item_a1", headers=BOB).status_code == 200


def test_negative_warehouse_detail_is_safe(client):
    assert client.get("/warehouses/wsp_alice", headers=BOB).status_code == 404


def test_negative_transfer_detail_is_safe(client):
    r = client.post(
        "/transfers", json={"item_id": "item_a1", "quantity": 1, "destination": "d"}, headers=ALICE
    )
    assert r.status_code == 201
    tid = r.json()["id"]
    assert client.get(f"/transfers/{tid}", headers=BOB).status_code == 404


def test_negative_transfer_bound_is_enforced(client):
    """Two transfers cannot total more than the item's stock (item_a1 has 40)."""
    r = client.post("/transfers", json={"item_id": "item_a1", "quantity": 40}, headers=ALICE)
    assert r.status_code == 201
    r = client.post("/transfers", json={"item_id": "item_a1", "quantity": 1}, headers=ALICE)
    assert r.status_code == 422
    item = client.get("/items/item_a1", headers=ALICE).json()
    assert Decimal(item["transferred"]) <= Decimal(item["quantity"])
