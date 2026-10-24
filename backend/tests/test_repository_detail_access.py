"""GET /repositories/{id} must enforce project membership, like the other repository routes."""

from __future__ import annotations


def _alice_repo(client_factory):
    alice = client_factory("alice")
    pid = alice.post("/api/v1/projects", json={"name": "p"}).json()["id"]
    body = {"full_name": "acme/detail", "installation_id": None, "default_branch": "main"}
    rid = alice.post(f"/api/v1/projects/{pid}/repositories", json=body).json()["id"]
    return alice, rid


def test_non_member_cannot_read_repository_detail(client_factory) -> None:
    alice, rid = _alice_repo(client_factory)
    bob = client_factory("bob")
    r = bob.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 404, r.text
    body = r.text
    assert "acme/detail" not in body
    assert "automatic_assessments" not in body
    assert "project_id" not in body


def test_owner_can_read_repository_detail(client_factory) -> None:
    alice, rid = _alice_repo(client_factory)
    r = alice.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == rid
    assert r.json()["full_name"] == "acme/detail"


def test_unauthenticated_repository_detail_is_401(client_factory) -> None:
    _, rid = _alice_repo(client_factory)
    assert client_factory().get(f"/api/v1/repositories/{rid}").status_code == 401


def test_unknown_repository_detail_is_404(client_factory) -> None:
    alice = client_factory("alice")
    assert alice.get("/api/v1/repositories/repo_does_not_exist").status_code == 404
