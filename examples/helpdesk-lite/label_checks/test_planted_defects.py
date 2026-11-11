"""Prove the planted defects in target/ exist and the lookalikes are really safe.

If one of these fails, someone fixed a planted defect or broke a lookalike, and the
evaluation labels no longer match the target. Run from examples/helpdesk-lite:
    target/.venv/bin/python -m pytest -q label_checks
"""

import sys
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "target"))
from helpdesk_lite.app import create_app  # noqa: E402

LABELS = yaml.safe_load((ROOT / "labels.yaml").read_text())
ALICE = {"Authorization": "Bearer fixture-token-alice"}
BOB = {"Authorization": "Bearer fixture-token-bob"}
CAROL = {"Authorization": "Bearer fixture-token-carol"}
TAUTOLOGY = "' OR '1'='1' --"
TRAVERSALS = (
    "../../../../../../../../etc/passwd",
    "....//....//....//....//etc/passwd",
    "/etc/passwd",
)


@pytest.fixture
def client():
    return TestClient(create_app())


def test_labels_reference_real_symbols():
    for f in LABELS["planted_findings"]:
        span = f["root_cause_span"]
        assert f"def {span['symbol']}(" in (ROOT / span["path"]).read_text(), f["id"]
    assert len(LABELS["planted_findings"]) == 4 and len(LABELS["negatives"]) == 5


def test_target_contains_no_answer_hints():
    for p in (ROOT / "target").rglob("*"):
        if p.is_file() and ".venv" not in p.parts and p.suffix in {".py", ".md", ".toml", ".csv"}:
            text = p.read_text(errors="ignore").lower()
            for hint in ("planted", "labels.yaml", "cwe-", "vulnerab"):
                assert hint not in text, (p, hint)


def test_planted_closed_ticket_is_readable_across_organizations(client):
    assert client.get("/tickets/tkt_a1", headers=BOB).status_code == 200
    assert client.get("/attachments/att_a1", headers=BOB).status_code == 200
    assert client.get("/tickets/tkt_a1", headers=ALICE).status_code == 200


def test_planted_report_answers_without_a_token(client):
    assert client.get("/reports/sla").status_code == 200
    assert client.get("/reports/sla", headers=ALICE).status_code == 200


def test_planted_ticket_search_leaks_other_organizations(client):
    benign = client.get("/tickets/search", params={"q": "no-such-term"}, headers=ALICE)
    assert benign.status_code == 200 and "tkt_b1" not in benign.text
    assert "tkt_b1" in client.get("/tickets/search", params={"q": TAUTOLOGY}, headers=ALICE).text


def test_planted_article_route_serves_a_file_outside_its_folder(client):
    ok = client.get("/help/articles", params={"file": "getting-started.md"}, headers=ALICE)
    assert ok.status_code == 200 and "root:" not in ok.text
    leaked = [
        "root:" in client.get("/help/articles", params={"file": t}, headers=ALICE).text
        for t in TRAVERSALS
    ]
    assert leaked == [False, False, True]


def test_negative_customer_detail_is_org_scoped(client):
    assert client.get("/customers/cus_a1", headers=BOB).status_code == 404
    assert client.get("/customers/cus_a1", headers=ALICE).status_code == 200


def test_negative_customer_search_binds_its_values(client):
    for payload in (TAUTOLOGY, "' OR 1=1 --", '" OR "1"="1" --'):
        r = client.get("/customers/search", params={"q": payload}, headers=ALICE)
        assert r.status_code == 200 and "cus_b1" not in r.text


def test_negative_export_download_stays_in_its_folder(client):
    ok = client.get("/exports/download", params={"file": "2026-10-tickets.csv"}, headers=ALICE)
    assert ok.status_code == 200
    for t in (*TRAVERSALS, "../org_bob/2026-10-tickets.csv"):
        r = client.get("/exports/download", params={"file": t}, headers=ALICE)
        assert r.status_code in (400, 404) and "root:" not in r.text and "tkt_b1" not in r.text


def test_negative_article_index_and_agent_list_need_a_token(client):
    assert client.get("/help/articles/index").status_code == 401
    assert client.get("/admin/agents").status_code == 401
    assert client.get("/admin/agents", headers=CAROL).status_code == 403


def test_open_tickets_are_org_scoped(client):
    assert client.get("/tickets/tkt_a2", headers=BOB).status_code == 404
