"""GET /repositories/{id} must enforce project membership, not just sign-in."""

from __future__ import annotations

from helpers import REPO


def test_non_member_cannot_read_repository(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    pid = alice.post("/api/v1/projects", json={"name": "payments-lite"}).json()["id"]
    r = alice.post(
        f"/api/v1/projects/{pid}/repositories", json={"full_name": REPO, "installation_id": None}
    )
    assert r.status_code == 201, r.text
    rid = r.json()["id"]

    owner_view = alice.get(f"/api/v1/repositories/{rid}")
    assert owner_view.status_code == 200, owner_view.text
    assert owner_view.json()["id"] == rid

    denied = bob.get(f"/api/v1/repositories/{rid}")
    assert denied.status_code == 404, denied.text
    assert "full_name" not in denied.json()

    missing = alice.get("/api/v1/repositories/does-not-exist")
    assert missing.status_code == 404


def test_unauthenticated_repository_read_is_401(client_factory) -> None:
    anon = client_factory()
    assert anon.get("/api/v1/repositories/any-id").status_code == 401
