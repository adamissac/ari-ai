"""GET /repositories/{repo_id} must enforce project membership (no cross-tenant read)."""

from __future__ import annotations

from helpers import setup_project


def test_other_identity_is_denied(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    mallory = client_factory("mallory")

    owner = alice.get(f"/api/v1/repositories/{ids['repo']}")
    assert owner.status_code == 200, owner.text
    assert owner.json()["id"] == ids["repo"]

    denied = mallory.get(f"/api/v1/repositories/{ids['repo']}")
    assert denied.status_code in (403, 404), denied.text
    assert "full_name" not in denied.text


def test_unauthenticated_read_is_rejected(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    anon = client_factory()
    assert anon.get(f"/api/v1/repositories/{ids['repo']}").status_code == 401


def test_missing_repository_is_not_found(client_factory) -> None:
    alice = client_factory("alice")
    r = alice.get("/api/v1/repositories/repo_does_not_exist")
    assert r.status_code == 404, r.text
    assert "repository" in r.text
