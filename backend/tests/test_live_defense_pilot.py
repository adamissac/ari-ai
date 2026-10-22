"""Live Defense Phase 2: staging apps, ingest health, analyst reviews, tenant isolation.

Accepting a recommendation must not enqueue jobs or call adapters. Health stays
unknown even when the HTTP status is 200.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
import sqlalchemy as sa
from helpers import setup_project

from backend.db import defense_recommendations, jobs, transaction
from shared import examples
from shared.base import utcnow
from shared.ids import IdPrefix, new_id


def _batch(end, requests: int, e4: int = 0, auth: int = 0, source: str = "runtime_demo") -> dict:
    return {
        "source": source,
        "window_start": (end - timedelta(minutes=1)).isoformat(),
        "window_end": end.isoformat(),
        "routes": [
            {
                "route": "GET /payments/{payment_id}",
                "requests": requests,
                "status_4xx": e4,
                "auth_failures": auth,
            }
        ],
    }


@pytest.fixture
def env(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    outsider = client_factory("mallory")
    outsider.post("/api/v1/projects", json={"name": "other-org"})
    return alice, bob, outsider, ids


def test_staging_app_onboarding_and_ingest_token_shown_once(env) -> None:
    alice, _, outsider, ids = env
    pid = ids["project"]
    created = alice.post(
        f"/api/v1/projects/{pid}/applications",
        json={"name": "payments staging", "environment": "owned_test"},
    )
    assert created.status_code == 201, created.text
    app = created.json()
    assert app["environment"] == "owned_test"
    assert app["shadow_mode"] is True
    assert app["ingest_configured"] is False
    assert app["verification"] == "unverified"
    assert "token" not in app

    forbidden_env = alice.post(
        f"/api/v1/projects/{pid}/applications",
        json={"name": "prod", "environment": "production"},
    )
    assert forbidden_env.status_code == 422

    outsider_hit = outsider.post(
        f"/api/v1/projects/{pid}/applications",
        json={"name": "steal", "environment": "sandbox"},
    )
    assert outsider_hit.status_code == 404

    minted = alice.post(f"/api/v1/applications/{app['id']}/ingest-tokens")
    assert minted.status_code == 201, minted.text
    body = minted.json()
    assert body["token"].startswith("hkt_ing_")
    token, token_id = body["token"], body["id"]

    listed = alice.get(f"/api/v1/projects/{pid}/ingest-tokens")
    assert listed.status_code == 200
    views = listed.json()["items"]
    assert len(views) == 1
    assert views[0]["id"] == token_id
    assert views[0]["application_id"] == app["id"]
    assert "token" not in views[0]
    assert token not in listed.text

    member_list = outsider.get(f"/api/v1/projects/{pid}/ingest-tokens")
    assert member_list.status_code == 404

    now = utcnow()
    ack = outsider.post(
        f"/api/v1/ingest/runtime/{pid}",
        json=_batch(now, 12),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ack.status_code == 202, ack.text

    other = alice.post("/api/v1/projects", json={"name": "other"}).json()["id"]
    cross = outsider.post(
        f"/api/v1/ingest/runtime/{other}",
        json=_batch(now + timedelta(minutes=1), 12),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cross.status_code == 401

    refreshed = alice.get(f"/api/v1/applications/{app['id']}").json()
    assert refreshed["ingest_configured"] is True
    assert refreshed["verification"] == "ingest_seen"
    assert refreshed["last_ingest_at"] is not None

    tokens = alice.get(f"/api/v1/projects/{pid}/ingest-tokens").json()["items"]
    assert tokens[0]["last_used_at"] is not None
    assert token not in alice.get(f"/api/v1/projects/{pid}/ingest-tokens").text


def test_defense_health_stays_unknown_on_http_200(env) -> None:
    alice, _, outsider, ids = env
    pid = ids["project"]
    r = alice.get(f"/api/v1/projects/{pid}/defense-health")
    assert r.status_code == 200, r.text
    health = r.json()
    assert health["status"] == "unknown"
    assert (
        "healthy" not in health["status_reason"].lower()
        or "not a healthy" in health["status_reason"]
    )
    assert health["last_ingest_at"] is None
    assert outsider.get(f"/api/v1/projects/{pid}/defense-health").status_code == 404

    graph = alice.get(f"/api/v1/projects/{pid}/defense-graph")
    assert graph.status_code == 200
    body = graph.json()
    assert body["nodes"] == []
    assert all(obs["state"] != "healthy" for obs in body["observations"])


def test_recorded_graph_marks_attention_not_healthy(env) -> None:
    alice, _, outsider, ids = env
    pid = ids["project"]
    app = alice.post(
        f"/api/v1/projects/{pid}/applications",
        json={"name": "demo app", "environment": "sandbox"},
    ).json()
    token = alice.post(f"/api/v1/applications/{app['id']}/ingest-tokens").json()["token"]
    now = utcnow()
    # Baseline window then a spike so scoring records an anomaly.
    assert (
        outsider.post(
            f"/api/v1/ingest/runtime/{pid}",
            json=_batch(now, 20),
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 202
    )
    spike = outsider.post(
        f"/api/v1/ingest/runtime/{pid}",
        json=_batch(now + timedelta(minutes=2), 20, e4=18, auth=18),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert spike.status_code == 202, spike.text

    graph = alice.get(f"/api/v1/projects/{pid}/defense-graph").json()
    states = {obs["state"] for obs in graph["observations"]}
    assert "healthy" not in states
    assert "unknown" in states
    assert any(obs["source"] == "ingest" for obs in graph["observations"])
    assert any(node["kind"] == "application" for node in graph["nodes"])
    health = alice.get(f"/api/v1/projects/{pid}/defense-health").json()
    assert health["status"] == "unknown"
    assert health["last_ingest_at"] is not None


def test_analyst_review_accept_does_not_execute(env) -> None:
    alice, bob, outsider, ids = env
    pid = ids["project"]
    rec0 = examples.build()["DefenseRecommendation"].model_dump(mode="json")
    rec_id = new_id(IdPrefix.rec)
    with transaction() as conn:
        conn.execute(
            sa.insert(defense_recommendations).values(
                id=rec_id, project_id=pid, doc={**rec0, "id": rec_id, "project_id": pid}
            )
        )
    with transaction() as conn:
        before = conn.execute(sa.select(sa.func.count()).select_from(jobs)).scalar()

    accepted = alice.post(
        f"/api/v1/defense-recommendations/{rec_id}/reviews",
        json={"decision": "accept", "reason": "Looks like a raise-monitoring suggestion only."},
    )
    assert accepted.status_code == 201, accepted.text
    review = accepted.json()
    assert review["decision"] == "accept"
    assert review["executes"] is False
    assert review["enforcement"] == "none"
    assert "apply" not in accepted.text.lower()

    rejected = bob.post(
        f"/api/v1/defense-recommendations/{rec_id}/reviews",
        json={"decision": "reject"},
    )
    assert rejected.status_code == 201
    investigate = alice.post(
        f"/api/v1/defense-recommendations/{rec_id}/reviews",
        json={"decision": "needs_investigation", "reason": "Need the linked event."},
    )
    assert investigate.status_code == 201

    history = alice.get(f"/api/v1/defense-recommendations/{rec_id}/reviews").json()["items"]
    assert [item["decision"] for item in history] == [
        "needs_investigation",
        "reject",
        "accept",
    ]
    project_history = alice.get(f"/api/v1/projects/{pid}/defense-reviews").json()["items"]
    assert len(project_history) == 3

    with transaction() as conn:
        after = conn.execute(sa.select(sa.func.count()).select_from(jobs)).scalar()
    assert after == before

    assert outsider.get(f"/api/v1/projects/{pid}/defense-reviews").status_code == 404
    assert (
        outsider.post(
            f"/api/v1/defense-recommendations/{rec_id}/reviews",
            json={"decision": "accept"},
        ).status_code
        == 404
    )


def test_tenant_isolation_on_live_defense_reads(env) -> None:
    alice, _, outsider, ids = env
    pid = ids["project"]
    app = alice.post(
        f"/api/v1/projects/{pid}/applications",
        json={"name": "isolated", "environment": "sandbox"},
    ).json()
    for path in (
        f"/api/v1/projects/{pid}/applications",
        f"/api/v1/applications/{app['id']}",
        f"/api/v1/projects/{pid}/defense-health",
        f"/api/v1/projects/{pid}/defense-graph",
        f"/api/v1/projects/{pid}/defense-reviews",
    ):
        assert outsider.get(path).status_code == 404, path
    assert outsider.post(f"/api/v1/applications/{app['id']}/ingest-tokens").status_code == 404
