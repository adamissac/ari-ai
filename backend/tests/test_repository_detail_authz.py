"""GET /repositories/{id} must enforce project membership, not just sign-in."""

import pytest
from helpers import setup_project


@pytest.fixture
def repo_ids(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    return alice, bob, ids


def test_other_identity_is_denied(repo_ids, client_factory):
    _, _, ids = repo_ids
    outsider = client_factory("outsider")
    r = outsider.get(f"/api/v1/repositories/{ids['repo']}")
    assert r.status_code == 404, r.text


def test_owner_still_reads_repository(repo_ids):
    alice, _, ids = repo_ids
    r = alice.get(f"/api/v1/repositories/{ids['repo']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == ids["repo"]
    assert "automatic_assessments" in body


def test_unknown_repository_is_not_found(repo_ids):
    alice, _, _ = repo_ids
    r = alice.get("/api/v1/repositories/does-not-exist")
    assert r.status_code == 404, r.text


def test_unauthenticated_is_rejected(repo_ids, client_factory):
    _, _, ids = repo_ids
    anon = client_factory()
    r = anon.get(f"/api/v1/repositories/{ids['repo']}")
    assert r.status_code == 401, r.text
