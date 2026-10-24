"""GET /projects/{id}/scopes must enforce project org membership (fail closed for non-members)."""

from __future__ import annotations

from helpers import add_member, setup_project


def test_unauthenticated_scope_listing_is_rejected(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    anon = client_factory()
    r = anon.get(f"/api/v1/projects/{ids['project']}/scopes")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_viewer_member_can_list_scopes(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    viewer = client_factory("carol")
    add_member(ids["org"], viewer.me["user"]["id"], "viewer")
    r = viewer.get(f"/api/v1/projects/{ids['project']}/scopes")
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["items"], list)
    assert r.json()["next_cursor"] is None


def test_non_member_gets_not_found_for_scope_listing(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    outsider = client_factory("eve")
    r = outsider.get(f"/api/v1/projects/{ids['project']}/scopes")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
