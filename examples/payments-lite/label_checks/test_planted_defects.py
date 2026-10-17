"""Prove the planted defects in target/ exist and the negatives are really safe.

If one of these fails, someone fixed a planted defect or broke a lookalike, and the
demo/evaluation labels no longer match the target. Run from examples/payments-lite:
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
from payments_lite.app import create_app  # noqa: E402

LABELS = yaml.safe_load((ROOT / "labels.yaml").read_text())
ALICE = {"Authorization": "Bearer fixture-token-alice"}
BOB = {"Authorization": "Bearer fixture-token-bob"}


@pytest.fixture
def client():
    return TestClient(create_app())


def test_labels_reference_real_symbols():
    src = (ROOT / "target/payments_lite/app.py").read_text()
    for f in LABELS["planted_findings"]:
        assert f"def {f['root_cause_span']['symbol']}(" in src
    assert {f["id"] for f in LABELS["planted_findings"]} == {
        "fnd_planted_authz",
        "fnd_planted_refund_bound",
    }


def test_target_contains_no_answer_hints():
    for p in (ROOT / "target").rglob("*"):
        if p.is_file() and ".venv" not in p.parts and p.suffix in {".py", ".md", ".toml", ""}:
            text = p.read_text(errors="ignore").lower()
            assert "planted" not in text and "labels.yaml" not in text, p


def test_planted_authz_exists(client):
    """exp_owner_only is violated: another customer's payment is readable."""
    assert client.get("/payments/pay_b1", headers=ALICE).status_code == 200


def test_planted_refund_bound_exists(client):
    """exp_refund_bound is violated: two refunds can total more than the payment."""
    for _ in range(2):
        r = client.post("/refunds", headers=ALICE, json={"payment_id": "pay_a2", "amount": "15.00"})
        assert r.status_code == 201
    refunded = Decimal(client.get("/payments/pay_a2", headers=ALICE).json()["refunded"])
    assert refunded > Decimal("15.50")


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "/customers/cus_bob", None),
        ("post", "/refunds", {"payment_id": "pay_b1", "amount": "1.00"}),
    ],
)
def test_negatives_are_safe(client, method, path, body):
    r = getattr(client, method)(path, headers=ALICE, **({"json": body} if body else {}))
    assert r.status_code == 404


def test_refund_negative_is_safe(client):
    ref = client.post(
        "/refunds", headers=BOB, json={"payment_id": "pay_b1", "amount": "2.00"}
    ).json()
    assert client.get(f"/refunds/{ref['id']}", headers=ALICE).status_code == 404
