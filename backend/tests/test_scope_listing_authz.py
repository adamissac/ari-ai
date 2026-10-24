"""Regression: GET /projects/{id}/scopes must enforce org membership (no cross-org scope leak)."""

from __future__ import annotations

from helpers import setup_project


def test_non_member_cannot_list_project_scopes(client_factory) -> None:
    alice, bob, eve = client_factory("alice"), client_factory("bob"), client_factory("eve")
    ids = setup_project(alice, bob, approve=True)
    r = eve.get(f"/api/v1/projects/{ids['project']}/scopes")
    assert r.status_code == 404, r.text
    assert "items" not in r.json()


def test_org_member_can_list_project_scopes_newest_first(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=True)
    for c in (alice, bob):
        r = c.get(f"/api/v1/projects/{ids['project']}/scopes")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["next_cursor"] is None
        assert [item["id"] for item in body["items"]] == [ids["scope"]]


def test_unauthenticated_scope_listing_is_rejected(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=True)
    r = client_factory().get(f"/api/v1/projects/{ids['project']}/scopes")
    assert r.status_code == 401
