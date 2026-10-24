"""Repository and snapshot viewer reads must enforce project membership (tenant isolation)."""

from __future__ import annotations

import sqlalchemy as sa
from helpers import add_member, setup_project

from backend.db import repositories, snapshots, transaction
from shared.base import utcnow
from shared.ids import IdPrefix, new_id


def _ready_snapshot(repo_id: str) -> str:
    sid = new_id(IdPrefix.snp)
    commit = "c" * 40
    created = utcnow()
    doc = {
        "id": sid,
        "repo_id": repo_id,
        "commit_sha": commit,
        "status": "ready",
        "index_version": "test",
        "created_at": created.isoformat(),
    }
    with transaction() as conn:
        conn.execute(
            sa.insert(snapshots).values(
                id=sid,
                repo_id=repo_id,
                commit_sha=commit,
                index_version="test",
                status="ready",
                doc=doc,
                created_at=created,
            )
        )
    return sid


def test_non_member_gets_404_on_viewer_reads(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    sid = _ready_snapshot(ids["repo"])
    mallory = client_factory("mallory")  # not a member of alice's organization

    assert mallory.get(f"/api/v1/repositories/{ids['repo']}").status_code == 404
    assert mallory.get(f"/api/v1/repositories/{ids['repo']}/snapshots").status_code == 404
    assert mallory.get(f"/api/v1/snapshots/{sid}").status_code == 404


def test_member_still_reads_repository_and_snapshots(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    sid = _ready_snapshot(ids["repo"])

    for client in (alice, bob):
        assert client.get(f"/api/v1/repositories/{ids['repo']}").status_code == 200
        assert client.get(f"/api/v1/repositories/{ids['repo']}/snapshots").status_code == 200
        assert client.get(f"/api/v1/snapshots/{sid}").status_code == 200


def test_viewer_member_reads_but_cannot_patch(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    carol = client_factory("carol")
    add_member(ids["org"], carol.me["user"]["id"], role="member")

    assert carol.get(f"/api/v1/repositories/{ids['repo']}").status_code == 200
    r = carol.patch(f"/api/v1/repositories/{ids['repo']}", json={"automatic_assessments": False})
    assert r.status_code == 403
