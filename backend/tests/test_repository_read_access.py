"""GET /repositories/{id} must enforce project membership (non-members get 404)."""

from helpers import add_member, setup_project


def test_repository_read_is_scoped_to_project_members(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    endpoint = f"/api/v1/repositories/{ids['repo']}"

    # Owner (alice) and co-owner (bob, added by setup_project) can read.
    assert alice.get(endpoint).status_code == 200
    assert alice.get(endpoint).json()["id"] == ids["repo"]

    # A signed-in user who is not a member of the project's org gets 404.
    carol = client_factory("carol")
    r = carol.get(endpoint)
    assert r.status_code == 404, r.text

    # Unknown repository still returns 404.
    assert alice.get("/api/v1/repositories/does-not-exist").status_code == 404


def test_viewer_member_can_read_repository(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    endpoint = f"/api/v1/repositories/{ids['repo']}"

    dave = client_factory("dave")
    org_id = alice.me["memberships"][0]["organization"]["id"]
    add_member(org_id, dave.me["user"]["id"], role="viewer")

    r = dave.get(endpoint)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == ids["repo"]


def test_unauthenticated_repository_read_is_401(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    anon = client_factory()
    assert anon.get(f"/api/v1/repositories/{ids['repo']}").status_code == 401
