"""GET /repositories/{id} must enforce project membership, like its sibling endpoints."""

from __future__ import annotations

from helpers import add_member, setup_project


def test_owner_gets_repository(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    r = alice.get(f"/api/v1/repositories/{ids['repo']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == ids["repo"]
    assert body["automatic_assessments"] is True


def test_project_member_gets_repository(client_factory) -> None:
    alice, bob, carol = client_factory("alice"), client_factory("bob"), client_factory("carol")
    ids = setup_project(alice, bob)
    add_member(ids["org"], carol.me["user"]["id"], role="member")
    r = carol.get(f"/api/v1/repositories/{ids['repo']}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == ids["repo"]


def test_non_member_gets_404_indistinguishable_from_missing(client_factory) -> None:
    alice, bob, mallory = client_factory("alice"), client_factory("bob"), client_factory("mallory")
    ids = setup_project(alice, bob)
    existing = mallory.get(f"/api/v1/repositories/{ids['repo']}")
    missing = mallory.get("/api/v1/repositories/repo_does_not_exist")
    assert existing.status_code == 404, existing.text
    assert missing.status_code == 404, missing.text
    # request_id is per-request; everything else must match exactly.
    strip = lambda r: {k: v for k, v in r.json()["error"].items() if k != "request_id"}  # noqa: E731
    assert strip(existing) == strip(missing)


def test_missing_repository_is_404_for_signed_in_user(client_factory) -> None:
    alice = client_factory("alice")
    r = alice.get("/api/v1/repositories/repo_does_not_exist")
    assert r.status_code == 404, r.text


def test_unauthenticated_is_401(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    anon = client_factory()
    assert anon.get(f"/api/v1/repositories/{ids['repo']}").status_code == 401
