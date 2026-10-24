"""GET /repositories/{repo_id} must enforce project membership like its sibling routes."""

import uuid

from helpers import setup_project


def test_other_identity_is_denied(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    mallory = client_factory("mallory")  # not a member of alice's organization

    r = mallory.get(f"/api/v1/repositories/{ids['repo']}")
    assert r.status_code == 404, r.text


def test_project_member_still_gets_repository(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)

    r = bob.get(f"/api/v1/repositories/{ids['repo']}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == ids["repo"]


def test_unknown_repo_returns_404_for_authenticated_user(client_factory):
    alice = client_factory("alice")
    r = alice.get(f"/api/v1/repositories/{uuid.uuid4()}")
    assert r.status_code == 404, r.text


def test_unauthenticated_get_is_rejected(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    anon = client_factory()

    r = anon.get(f"/api/v1/repositories/{ids['repo']}")
    assert r.status_code != 200, r.text
