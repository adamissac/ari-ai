"""Regression: GET /projects/{id}/scopes must enforce project membership like its siblings."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from helpers import add_member, setup_project


def _foreign_project_with_scope(owner, co_owner) -> dict[str, str]:
    """Build a second org's project + scope under a different repo name (REPO is taken)."""
    org_id = owner.me["memberships"][0]["organization"]["id"]
    add_member(org_id, co_owner.me["user"]["id"])
    pid = owner.post(
        "/api/v1/projects",
        json={"name": "other", "settings": {"delivery_mode": "manual"}},
    ).json()["id"]
    rid = owner.post(
        f"/api/v1/projects/{pid}/repositories",
        json={"full_name": "acme/other-lite", "installation_id": None},
    ).json()["id"]
    sid = owner.post(
        f"/api/v1/projects/{pid}/scopes",
        json={
            "name": "foreign",
            "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            "targets": [
                {
                    "kind": "sandbox_build",
                    "repo_id": rid,
                    "build_recipe_ref": "examples/payments-lite/sandbox.yaml",
                    "exposed_ports": [8080],
                }
            ],
            "allowed_check_categories": ["authorization.ownership"],
        },
    )
    assert sid.status_code == 201, sid.text
    return {"project": pid, "scope": sid.json()["id"]}


def test_non_member_cannot_list_scopes_of_a_project(client_factory) -> None:
    alice, bob, eve = client_factory("alice"), client_factory("bob"), client_factory("eve")
    ids = setup_project(alice, bob)
    r = eve.get(f"/api/v1/projects/{ids['project']}/scopes")
    assert r.status_code == 404
    assert ids["scope"] not in r.text
    assert "items" not in r.json()


def test_unauthenticated_cannot_list_scopes(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    anon = client_factory()
    r = anon.get(f"/api/v1/projects/{ids['project']}/scopes")
    assert r.status_code == 401


def test_owner_and_viewer_see_only_their_project_scopes_newest_first(client_factory) -> None:
    alice, bob, viewer, eve, mallory = (
        client_factory("alice"),
        client_factory("bob"),
        client_factory("vicviewer"),
        client_factory("eve"),
        client_factory("mallory"),
    )
    ids = setup_project(alice, bob)
    add_member(ids["org"], viewer.me["user"]["id"], "viewer")

    # A scope in a different organisation must never leak into alice's listing.
    other = _foreign_project_with_scope(eve, mallory)

    owner = alice.get(f"/api/v1/projects/{ids['project']}/scopes")
    assert owner.status_code == 200, owner.text
    owner_ids = [item["id"] for item in owner.json()["items"]]
    assert owner_ids == [ids["scope"]]
    assert other["scope"] not in owner_ids
    assert owner.json()["next_cursor"] is None

    seen_by_viewer = viewer.get(f"/api/v1/projects/{ids['project']}/scopes")
    assert seen_by_viewer.status_code == 200, seen_by_viewer.text
    assert [item["id"] for item in seen_by_viewer.json()["items"]] == [ids["scope"]]

    # The other org's owner still sees only their own project's scope.
    eve_view = eve.get(f"/api/v1/projects/{other['project']}/scopes")
    assert eve_view.status_code == 200
    assert [item["id"] for item in eve_view.json()["items"]] == [other["scope"]]
