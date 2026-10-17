"""GET /repositories/{repo_id}/snapshots — Vihaan's M6 API ask (b)."""

from __future__ import annotations

import sqlalchemy as sa
from helpers import setup_project

from backend.db import snapshots, transaction


def test_snapshot_list_is_scoped_filtered_and_paged(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    eve = client_factory("eve")
    ids = setup_project(alice, bob)
    url = f"/api/v1/repositories/{ids['repo']}/snapshots"
    made = [alice.post(url, json={"commit_sha": c * 40}).json()["id"] for c in ("a", "b", "c")]
    with transaction() as conn:  # mark one ready as the indexer would
        doc = conn.execute(sa.select(snapshots.c.doc).where(snapshots.c.id == made[1])).scalar()
        conn.execute(
            sa.update(snapshots)
            .where(snapshots.c.id == made[1])
            .values(status="ready", doc={**doc, "status": "ready"})
        )

    page = alice.get(url, params={"limit": 2}).json()
    assert [s["id"] for s in page["items"]] == made[::-1][:2]
    rest = alice.get(url, params={"limit": 2, "cursor": page["next_cursor"]}).json()
    assert [s["id"] for s in rest["items"]] == [made[0]] and rest["next_cursor"] is None

    ready = alice.get(url, params={"status": "ready"}).json()["items"]
    assert [(s["id"], s["status"]) for s in ready] == [(made[1], "ready")]
    assert alice.get(url, params={"status": "bogus"}).status_code == 422
    assert eve.get(url).status_code == 404  # not a member: existence not revealed
