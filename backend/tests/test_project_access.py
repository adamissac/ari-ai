"""GET /projects/{id} must enforce org membership, like the other project routes."""

from __future__ import annotations


def test_owner_gets_project_body(client_factory) -> None:
    alice = client_factory("alice")
    pid = alice.post("/api/v1/projects", json={"name": "secret-proj"}).json()["id"]
    r = alice.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == pid
    assert body["name"] == "secret-proj"
    assert "settings" in body


def test_non_member_gets_404_without_leak(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    pid = alice.post("/api/v1/projects", json={"name": "secret-proj"}).json()["id"]
    r = bob.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 404, r.text
    assert "secret-proj" not in r.text
    assert "settings" not in r.text
    # Same answer as for a project that does not exist at all.
    missing = bob.get("/api/v1/projects/prj_does_not_exist")
    assert missing.status_code == 404
    assert r.json()["error"]["code"] == missing.json()["error"]["code"]
    assert r.json()["error"]["message"] == missing.json()["error"]["message"]


def test_unauthenticated_gets_401(client_factory) -> None:
    alice, anon = client_factory("alice"), client_factory()
    pid = alice.post("/api/v1/projects", json={"name": "secret-proj"}).json()["id"]
    assert anon.get(f"/api/v1/projects/{pid}").status_code == 401
