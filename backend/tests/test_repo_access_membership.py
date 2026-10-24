"""Repository and snapshot reads require project membership (viewer included)."""

from __future__ import annotations

from helpers import add_member, setup_project

HEAD_SHA = "a" * 40


def test_non_member_cannot_read_repo_snapshots_or_snapshot(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    eve = client_factory("eve")
    ids = setup_project(alice, bob)
    repo_url = f"/api/v1/repositories/{ids['repo']}"
    snaps_url = f"{repo_url}/snapshots"
    snap_id = alice.post(snaps_url, json={"commit_sha": HEAD_SHA}).json()["id"]

    assert eve.get(repo_url).status_code == 404
    assert eve.get(snaps_url).status_code == 404
    assert eve.get(f"/api/v1/snapshots/{snap_id}").status_code == 404
    assert eve.patch(repo_url, json={"automatic_assessments": False}).status_code == 404
    assert eve.post(snaps_url, json={"commit_sha": "c" * 40}).status_code == 404

    # owner keeps read access
    assert alice.get(repo_url).status_code == 200
    assert alice.get(snaps_url).status_code == 200
    assert alice.get(f"/api/v1/snapshots/{snap_id}").status_code == 200


def test_viewer_can_read_but_not_write(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    viewer = client_factory("eve")
    ids = setup_project(alice, bob)
    org_id = alice.me["memberships"][0]["organization"]["id"]
    add_member(org_id, viewer.me["user"]["id"], role="viewer")
    repo_url = f"/api/v1/repositories/{ids['repo']}"

    assert viewer.get(repo_url).status_code == 200
    assert viewer.get(f"{repo_url}/snapshots").status_code == 200
    assert viewer.patch(repo_url, json={"automatic_assessments": False}).status_code == 403
    assert viewer.post(f"{repo_url}/snapshots", json={"commit_sha": "c" * 40}).status_code == 403


def test_missing_repo_is_not_found(client_factory) -> None:
    alice = client_factory("alice")
    missing = "/api/v1/repositories/repo_does_not_exist"
    assert alice.get(missing).status_code == 404
    assert alice.get(f"{missing}/snapshots").status_code == 404
