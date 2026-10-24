"""GET /projects/{id} must enforce org membership, like the sibling project routes."""

from __future__ import annotations


def test_other_identity_is_denied(client_factory) -> None:
    alice, eve = client_factory("alice"), client_factory("eve")
    pid = alice.post("/api/v1/projects", json={"name": "secret"}).json()["id"]
    r = eve.get(f"/api/v1/projects/{pid}")
    assert r.status_code in (403, 404), r.text
    assert "secret" not in r.text


def test_owner_still_reads_project(client_factory) -> None:
    alice = client_factory("alice")
    pid = alice.post("/api/v1/projects", json={"name": "mine"}).json()["id"]
    r = alice.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == pid and r.json()["name"] == "mine"


def test_unauthenticated_get_project_is_401(client_factory) -> None:
    alice = client_factory("alice")
    pid = alice.post("/api/v1/projects", json={"name": "x"}).json()["id"]
    assert client_factory().get(f"/api/v1/projects/{pid}").status_code == 401
