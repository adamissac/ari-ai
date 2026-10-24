"""GET /api/v1/repositories/{id} must enforce project membership, like the other repo routes."""

from __future__ import annotations

from helpers import REPO, add_member, setup_project


def _repo_id(alice, bob) -> str:
    ids = setup_project(alice, bob)
    return ids["repo"]


def test_non_member_gets_404_without_repository_body(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    rid = _repo_id(alice, bob)
    eve = client_factory("eve")  # signed in, but not a member of alice's project
    r = eve.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 404, r.text
    body = r.json()
    assert "full_name" not in body and "id" not in body
    assert REPO not in r.text


def test_project_member_gets_repository(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    rid = _repo_id(alice, bob)
    r = alice.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == rid
    assert body["full_name"] == REPO
    assert "automatic_assessments" in body


def test_viewer_member_gets_repository(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    rid = _repo_id(alice, bob)
    carol = client_factory("carol")
    org_id = alice.me["memberships"][0]["organization"]["id"]
    add_member(org_id, carol.me["user"]["id"], role="viewer")
    r = carol.get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == rid


def test_unknown_repository_is_404(client_factory) -> None:
    alice = client_factory("alice")
    r = alice.get("/api/v1/repositories/repo_does_not_exist")
    assert r.status_code == 404, r.text


def test_unauthenticated_is_rejected(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    rid = _repo_id(alice, bob)
    r = client_factory().get(f"/api/v1/repositories/{rid}")
    assert r.status_code == 401, r.text
