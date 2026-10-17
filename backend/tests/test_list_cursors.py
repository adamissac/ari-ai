"""Capped list endpoints used to return next_cursor=null even when they truncated
(monitoring feed at `limit`, defense recommendations at 50, audit at 500), so older rows
were unreachable. They now page with real cursors; every row is reachable exactly once."""

from __future__ import annotations

import sqlalchemy as sa
from helpers import setup_project

from backend import audit
from backend.db import defense_recommendations, monitoring_events, transaction
from shared import examples
from shared.audit import ActorType


def _walk(client, url, params, cursor_key="cursor"):
    seen, cursor, pages = [], None, 0
    while True:
        q = dict(params, **({cursor_key: cursor} if cursor else {}))
        r = client.get(url, params=q)
        assert r.status_code == 200, r.text
        body = r.json()
        pages += 1
        seen += [i["id"] for i in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            return seen, pages
        assert pages < 50


def test_monitoring_feed_and_recommendations_page_through_everything(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    pid = ids["project"]
    ex = examples.build()
    ev0 = ex["MonitoringEvent"].model_dump(mode="json")
    rec0 = ex["DefenseRecommendation"].model_dump(mode="json")
    with transaction() as conn:  # one transaction: identical created_at, id breaks the tie
        for i in range(7):
            eid = f"evt_cursor{i:04d}"
            conn.execute(
                sa.insert(monitoring_events).values(
                    id=eid,
                    project_id=pid,
                    repo_id=ids["repo"],
                    dedupe_key=f"cursor-{i}",
                    status=ev0["status"],
                    doc={**ev0, "id": eid, "project_id": pid, "repo_id": ids["repo"]},
                )
            )
            rid = f"rec_cursor{i:04d}"
            conn.execute(
                sa.insert(defense_recommendations).values(
                    id=rid, project_id=pid, doc={**rec0, "id": rid, "project_id": pid}
                )
            )
    events, pages = _walk(alice, f"/api/v1/projects/{pid}/events", {"limit": 3})
    assert sorted(events) == [f"evt_cursor{i:04d}" for i in range(7)] and len(set(events)) == 7
    assert pages == 3
    recs, _ = _walk(alice, f"/api/v1/projects/{pid}/defense-recommendations", {"limit": 3})
    assert sorted(recs) == [f"rec_cursor{i:04d}" for i in range(7)] and len(set(recs)) == 7
    for bad in ("nonsense", "2026-10-17T00:00:00", "|rec_x"):
        r = alice.get(f"/api/v1/projects/{pid}/events", params={"cursor": bad})
        assert r.status_code == 422, (bad, r.text)


def test_audit_log_pages_by_seq(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    pid = ids["project"]
    org = alice.me["memberships"][0]["organization"]["id"]
    with transaction() as conn:
        for i in range(6):
            audit.record(
                conn,
                org_id=org,
                project_id=pid,
                actor_type=ActorType.system,
                actor_id="test",
                action="test.cursor",
                subject_type="project",
                subject_id=pid,
                details={"i": i},
            )
    full = alice.get("/api/v1/audit", params={"project_id": pid}).json()
    assert full["next_cursor"] is None and full["chain_verified"] is True
    expected = [e["id"] for e in full["items"]]
    walked, pages = _walk(alice, "/api/v1/audit", {"project_id": pid, "limit": 4})
    assert walked == expected and pages >= 2
    assert alice.get("/api/v1/audit", params={"project_id": pid, "cursor": "x"}).status_code == 422
