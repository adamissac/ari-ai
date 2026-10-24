"""Regression: GET /projects/{id}/scopes must enforce project membership (non-members get 404)."""

from __future__ import annotations

from helpers import setup_project


def test_scope_listing_is_limited_to_project_members(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)

    # Owner of project A can list its scopes.
    r = alice.get(f"/api/v1/projects/{ids['project']}/scopes")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["next_cursor"] is None
    assert [item["id"] for item in body["items"]] == [ids["scope"]]

    # A user from another org (project B) must not see project A's scopes.
    carol = client_factory("carol")
    pb = carol.post("/api/v1/projects", json={"name": "other-org-project"})
    assert pb.status_code == 201, pb.text
    other_pid = pb.json()["id"]
    assert carol.get(f"/api/v1/projects/{other_pid}/scopes").status_code == 200

    r = carol.get(f"/api/v1/projects/{ids['project']}/scopes")
    assert r.status_code == 404, r.text
    assert ids["scope"] not in r.text
    assert "items" not in r.json()


def test_scope_listing_requires_authentication(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    r = client_factory().get(f"/api/v1/projects/{ids['project']}/scopes")
    assert r.status_code == 401, r.text
