"""GET /repositories/{id} must enforce project membership, without leaking existence."""

from helpers import setup_project


def _ids(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    return alice, bob, ids


def test_non_member_gets_404_for_existing_repository(client_factory):
    alice, bob, ids = _ids(client_factory)
    carol = client_factory("carol")  # signed in, but not a member of alice's organization
    assert alice.get(f"/api/v1/repositories/{ids['repo']}").status_code == 200
    response = carol.get(f"/api/v1/repositories/{ids['repo']}")
    assert response.status_code == 404, response.text
    assert "full_name" not in response.text
    assert "automatic_assessments" not in response.text


def test_non_member_404_matches_missing_repository(client_factory):
    alice, bob, ids = _ids(client_factory)
    carol = client_factory("carol")
    existing = carol.get(f"/api/v1/repositories/{ids['repo']}")
    missing = carol.get("/api/v1/repositories/rep_does_not_exist")
    assert existing.status_code == missing.status_code == 404
    # request_id is per-request, so compare the error payload without it
    assert existing.json()["error"]["code"] == missing.json()["error"]["code"] == "NOT_FOUND"
    assert existing.json()["error"]["message"] == missing.json()["error"]["message"]
    assert existing.json()["error"]["details"] == missing.json()["error"]["details"]


def test_member_and_owner_still_get_the_repository(client_factory):
    alice, bob, ids = _ids(client_factory)
    owner = alice.get(f"/api/v1/repositories/{ids['repo']}")
    member = bob.get(f"/api/v1/repositories/{ids['repo']}")
    assert owner.status_code == 200, owner.text
    assert member.status_code == 200, member.text
    assert owner.json() == member.json()
    assert owner.json()["id"] == ids["repo"]


def test_unauthenticated_gets_401(client_factory):
    alice, bob, ids = _ids(client_factory)
    anon = client_factory()
    assert anon.get(f"/api/v1/repositories/{ids['repo']}").status_code == 401
