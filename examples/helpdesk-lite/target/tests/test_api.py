"""Intended-behavior tests for helpdesk-lite."""

from fastapi.testclient import TestClient

from helpdesk_lite.app import create_app

client = TestClient(create_app())
ALICE = {"Authorization": "Bearer fixture-token-alice"}
BOB = {"Authorization": "Bearer fixture-token-bob"}
CAROL = {"Authorization": "Bearer fixture-token-carol"}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_requires_token():
    assert client.get("/tickets").status_code == 401
    assert client.get("/customers/cus_a1").status_code == 401


def test_me():
    assert client.get("/me", headers=ALICE).json()["org_id"] == "org_alice"


def test_agent_lists_own_tickets():
    ids = [t["id"] for t in client.get("/tickets", headers=ALICE).json()]
    assert ids == ["tkt_a1", "tkt_a2"]


def test_agent_reads_own_ticket():
    r = client.get("/tickets/tkt_a2", headers=ALICE)
    assert r.status_code == 200 and r.json()["subject"] == "Login loop on mobile"


def test_open_ticket_of_another_org_is_hidden():
    assert client.get("/tickets/tkt_a2", headers=BOB).status_code == 404


def test_customer_of_another_org_is_hidden():
    assert client.get("/customers/cus_a1", headers=BOB).status_code == 404
    assert client.get("/customers/cus_a1", headers=ALICE).json()["name"] == "Ada Park"


def test_ticket_search_finds_own_tickets():
    hits = client.get("/tickets/search", params={"q": "login"}, headers=ALICE).json()
    assert [h["id"] for h in hits] == ["tkt_a2"]
    assert client.get("/tickets/search", params={"q": "invoice"}, headers=ALICE).json() == []


def test_customer_search_matches_name_or_email():
    hits = client.get("/customers/search", params={"q": "ada@"}, headers=ALICE).json()
    assert [h["id"] for h in hits] == ["cus_a1"]
    assert client.get("/customers/search", params={"q": "ben"}, headers=ALICE).json() == []


def test_attachment_of_own_ticket():
    assert (
        client.get("/attachments/att_a1", headers=ALICE).json()["filename"] == "bank-statement.pdf"
    )


def test_help_article():
    r = client.get("/help/articles", params={"file": "getting-started.md"}, headers=CAROL)
    assert r.status_code == 200 and r.text.startswith("# Getting started")
    assert client.get("/help/articles/index", headers=CAROL).json() == [
        "getting-started.md",
        "sla-policy.md",
    ]
    assert (
        client.get("/help/articles", params={"file": "../store.py"}, headers=CAROL).status_code
        == 400
    )


def test_export_download_is_per_org():
    r = client.get("/exports/download", params={"file": "2026-10-tickets.csv"}, headers=ALICE)
    assert r.status_code == 200 and "tkt_a1" in r.text and "tkt_b1" not in r.text
    escape = {"file": "../org_bob/2026-10-tickets.csv"}
    assert client.get("/exports/download", params=escape, headers=ALICE).status_code == 400


def test_close_ticket():
    fresh = TestClient(create_app())
    assert fresh.post("/tickets/tkt_a2/close", headers=ALICE).json()["status"] == "closed"
    assert fresh.post("/tickets/tkt_b2/close", headers=ALICE).status_code == 404


def test_only_admins_list_agents():
    assert [a["id"] for a in client.get("/admin/agents", headers=ALICE).json()] == [
        "agt_alice",
        "agt_carol",
    ]
    assert client.get("/admin/agents", headers=CAROL).status_code == 403


def test_sla_targets():
    assert client.get("/reports/sla", headers=ALICE).json()["first_reply_hours"] == 4
