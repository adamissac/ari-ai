"""GET /repositories/{id} must enforce project membership (non-members get 404)."""

from __future__ import annotations


def _alice_repo(client_factory):
    alice = client_factory("alice")
    pid = alice.post("/api/v1/projects", json={"name": "p"}).json()["id"]
    r = alice.post(
        f"/api/v1/projects/{pid}/repositories",
        json={"full_name": "acme/shop", "installation_id": None},
    )
    assert r.status_code == 201, r.text
    return alice, r.json()["id"]


def test_owner_can_read_repository(client_factory) -> None:
    alice, rid = _alice_repo(client_factory)
    r = alice.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == rid


def test_non_member_cannot_read_repository(client_factory) -> None:
    alice, rid = _alice_repo(client_factory)
    bob = client_factory("bob")
    assert bob.get(f"/api/v1/repositories/{rid}").status_code == 404


def test_unknown_repository_is_not_found(client_factory) -> None:
    alice = client_factory("alice")
    assert alice.get("/api/v1/repositories/rep_does_not_exist").status_code == 404


def test_unauthenticated_read_is_rejected(client_factory) -> None:
    alice, rid = _alice_repo(client_factory)
    anon = client_factory()
    assert anon.get(f"/api/v1/repositories/{rid}").status_code == 401
