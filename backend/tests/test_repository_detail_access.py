"""GET /repositories/{repo_id} must enforce project membership (tenant isolation)."""

from __future__ import annotations


def _owned_repo(client_factory):
    alice = client_factory("alice")
    pid = alice.post("/api/v1/projects", json={"name": "p"}).json()["id"]
    body = {"full_name": "acme/detail", "installation_id": None, "default_branch": "main"}
    rid = alice.post(f"/api/v1/projects/{pid}/repositories", json=body).json()["id"]
    return alice, rid


def test_owner_can_read_repository_detail(client_factory) -> None:
    alice, rid = _owned_repo(client_factory)
    r = alice.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == rid
    assert body["full_name"] == "acme/detail"
    assert body["project_id"]


def test_non_member_cannot_read_repository_detail(client_factory) -> None:
    alice, rid = _owned_repo(client_factory)
    bob = client_factory("bob")
    r = bob.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 404, r.text
    assert "acme/detail" not in r.text


def test_non_member_gets_same_response_as_unknown_id(client_factory) -> None:
    alice, rid = _owned_repo(client_factory)
    bob = client_factory("bob")
    denied = bob.get(f"/api/v1/repositories/{rid}")
    unknown = bob.get("/api/v1/repositories/repo_does_not_exist")
    assert denied.status_code == unknown.status_code == 404
    assert denied.json()["error"]["code"] == unknown.json()["error"]["code"] == "NOT_FOUND"


def test_unknown_repository_is_not_found(client_factory) -> None:
    alice = client_factory("alice")
    r = alice.get("/api/v1/repositories/repo_does_not_exist")
    assert r.status_code == 404, r.text


def test_unauthenticated_repository_detail_is_rejected(client_factory) -> None:
    alice, rid = _owned_repo(client_factory)
    anon = client_factory()
    r = anon.get(f"/api/v1/repositories/{rid}")
    assert 400 <= r.status_code < 500, r.text
    assert r.status_code != 200
