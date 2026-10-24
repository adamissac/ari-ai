"""GET /repositories/{repo_id} must enforce project membership, like the other repo routes."""

from __future__ import annotations


def _owned_repo(alice):
    pid = alice.post("/api/v1/projects", json={"name": "p"}).json()["id"]
    body = {"full_name": "acme/detail", "installation_id": None, "default_branch": "main"}
    r = alice.post(f"/api/v1/projects/{pid}/repositories", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_non_member_cannot_read_repository_record(client_factory) -> None:
    alice = client_factory("alice")
    bob = client_factory("bob")
    rid = _owned_repo(alice)
    assert alice.get(f"/api/v1/repositories/{rid}").status_code == 200
    r = bob.get(f"/api/v1/repositories/{rid}")
    assert r.status_code in (403, 404), r.text
    assert "full_name" not in r.text
    assert "acme/detail" not in r.text


def test_member_still_gets_repository_record(client_factory) -> None:
    alice = client_factory("alice")
    rid = _owned_repo(alice)
    r = alice.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == rid
    assert r.json()["full_name"] == "acme/detail"


def test_unauthenticated_repository_read_is_401(client_factory) -> None:
    alice = client_factory("alice")
    rid = _owned_repo(alice)
    anon = client_factory()
    assert anon.get(f"/api/v1/repositories/{rid}").status_code == 401


def test_unknown_repository_is_404(client_factory) -> None:
    alice = client_factory("alice")
    r = alice.get("/api/v1/repositories/repo_does_not_exist")
    assert r.status_code == 404
