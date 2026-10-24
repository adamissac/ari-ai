"""GET /api/v1/repositories/{id} must enforce project membership (tenant isolation)."""

from __future__ import annotations


def _alice_repo(client_factory):
    alice = client_factory("alice")
    pid = alice.post("/api/v1/projects", json={"name": "p"}).json()["id"]
    rid = alice.post(
        f"/api/v1/projects/{pid}/repositories", json={"full_name": "acme/shop"}
    ).json()["id"]
    return alice, rid


def test_other_identity_is_denied(client_factory) -> None:
    alice, rid = _alice_repo(client_factory)
    bob = client_factory("bob")
    assert alice.get(f"/api/v1/repositories/{rid}").status_code == 200
    r = bob.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 404, r.text


def test_member_still_gets_repository_body(client_factory) -> None:
    alice, rid = _alice_repo(client_factory)
    r = alice.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == rid
    assert r.json()["full_name"] == "acme/shop"


def test_unknown_repository_is_not_found(client_factory) -> None:
    alice = client_factory("alice")
    r = alice.get("/api/v1/repositories/does-not-exist")
    assert r.status_code == 404, r.text


def test_unauthenticated_get_is_rejected(client_factory) -> None:
    _, rid = _alice_repo(client_factory)
    anon = client_factory()
    assert anon.get(f"/api/v1/repositories/{rid}").status_code == 401
