"""GET /repositories/{id} must enforce project/org membership, like PATCH does."""

from __future__ import annotations

from helpers import add_member


def _alice_repo(client_factory):
    alice = client_factory("alice")
    org_id = alice.me["memberships"][0]["organization"]["id"]
    pid = alice.post("/api/v1/projects", json={"name": "payments-lite"}).json()["id"]
    r = alice.post(
        f"/api/v1/projects/{pid}/repositories",
        json={"full_name": "acme/payments-lite", "installation_id": None},
    )
    assert r.status_code == 201, r.text
    return alice, org_id, r.json()


def test_non_member_cannot_read_repository(client_factory) -> None:
    alice, _, repo = _alice_repo(client_factory)
    mallory = client_factory("mallory")
    r = mallory.get(f"/api/v1/repositories/{repo['id']}")
    assert r.status_code in (403, 404), r.text
    body = r.json()
    assert "full_name" not in body
    assert "acme/payments-lite" not in r.text


def test_member_can_read_repository(client_factory) -> None:
    alice, org_id, repo = _alice_repo(client_factory)
    bob = client_factory("bob")
    add_member(org_id, bob.me["user"]["id"], role="viewer")
    r = bob.get(f"/api/v1/repositories/{repo['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == repo["id"]
    assert r.json()["full_name"] == "acme/payments-lite"


def test_unauthenticated_read_is_401(client_factory) -> None:
    _, _, repo = _alice_repo(client_factory)
    anon = client_factory()
    assert anon.get(f"/api/v1/repositories/{repo['id']}").status_code == 401


def test_missing_repository_is_404(client_factory) -> None:
    alice, _, _ = _alice_repo(client_factory)
    r = alice.get("/api/v1/repositories/does-not-exist")
    assert r.status_code == 404
    assert "repository" in r.text
