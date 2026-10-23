"""Live Defense Phase 3: authenticated ingest, rules, shadow decisions, no enforcement."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from helpers import setup_project

from backend import worker
from backend.db import jobs, live_policy_decisions, transaction
from backend.live_defense.quarantine import secret_like_reason
from shared.base import utcnow
from shared.ids import IdPrefix, new_id

ROUTE = "GET /payments/{payment_id}"


def _batch(
    end,
    requests: int,
    e4: int = 0,
    auth: int = 0,
    source: str = "owned_staging",
    principals: list[dict] | None = None,
    extra_routes: list[dict] | None = None,
) -> dict:
    route = {
        "route": ROUTE,
        "requests": requests,
        "status_4xx": e4,
        "auth_failures": auth,
    }
    if principals is not None:
        route["principals"] = principals
    routes = [route]
    if extra_routes:
        routes.extend(extra_routes)
    return {
        "source": source,
        "window_start": (end - timedelta(minutes=1)).isoformat(),
        "window_end": end.isoformat(),
        "routes": routes,
    }


@pytest.fixture
def env(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    outsider = client_factory("mallory")
    outsider.post("/api/v1/projects", json={"name": "other-org"})
    app = alice.post(
        f"/api/v1/projects/{ids['project']}/applications",
        json={"name": "payments-lite staging", "environment": "owned_test"},
    ).json()
    token = alice.post(f"/api/v1/applications/{app['id']}/ingest-tokens").json()["token"]
    ids["app"] = app["id"]
    ids["token"] = token
    return alice, bob, outsider, ids, client_factory()


def _ingest(client, ids, body: dict):
    return client.post(
        f"/api/v1/ingest/runtime/{ids['project']}",
        json=body,
        headers={"Authorization": f"Bearer {ids['token']}"},
    )


def test_owned_staging_ingest_is_authenticated_not_replay(env) -> None:
    alice, _, outsider, ids, anon = env
    now = utcnow()
    ack = _ingest(anon, ids, _batch(now, 20, e4=18, auth=18))
    assert ack.status_code == 202, ack.text
    worker.drain(kinds=["live_defense_shadow"])
    events = alice.get(f"/api/v1/projects/{ids['project']}/events").json()["items"]
    assert events, "authenticated ingest should record events"
    assert all(item["simulated"] is False for item in events)
    assert all("replay" not in (item.get("status_reason") or "").lower() for item in events)
    page = alice.get(f"/api/v1/projects/{ids['project']}/live-policy-decisions").json()
    assert page["items"], page
    decision = page["items"][0]
    assert decision["simulated"] is False
    assert decision["telemetry_source"] == "owned_staging"
    assert decision["enforcement"] == "NOT_EXECUTED"
    assert decision["executed"] is False
    assert decision["rules_ran"] is True
    assert "replay" not in decision["caveat"].lower()
    assert (
        outsider.get(f"/api/v1/projects/{ids['project']}/live-policy-decisions").status_code == 404
    )


def test_owned_staging_requires_application_token(env) -> None:
    alice, _, _, ids, anon = env
    project_token = alice.post(f"/api/v1/projects/{ids['project']}/ingest-tokens").json()["token"]
    now = utcnow()
    r = anon.post(
        f"/api/v1/ingest/runtime/{ids['project']}",
        json=_batch(now, 4),
        headers={"Authorization": f"Bearer {project_token}"},
    )
    assert r.status_code == 422
    assert "application-bound" in r.text


def test_secret_like_payload_is_quarantined_and_not_stored(env) -> None:
    alice, _, _, ids, anon = env
    now = utcnow()
    body = _batch(now, 4)
    body["routes"][0]["note"] = "Bearer supersecret"
    r = _ingest(anon, ids, body)
    assert r.status_code == 422
    assert "secret-like" in r.text
    events = alice.get(f"/api/v1/projects/{ids['project']}/events").json()["items"]
    ignored = [e for e in events if e["status"] == "ignored"]
    assert ignored
    assert "supersecret" not in alice.get(f"/api/v1/projects/{ids['project']}/events").text
    assert secret_like_reason({"authorization": "Bearer abc"}) is not None
    assert secret_like_reason({"routes": [{"route": "GET /health", "requests": 1}]}) is None


def test_http_200_is_not_idor_and_v6_does_not_silently_decide(env) -> None:
    _, _, _, ids, anon = env
    now = utcnow()
    ack = _ingest(anon, ids, _batch(now, 15))
    assert ack.status_code == 202, ack.text
    worker.drain(kinds=["live_defense_shadow"])
    with transaction() as conn:
        docs = list(
            conn.execute(
                sa.select(live_policy_decisions.c.doc).where(
                    live_policy_decisions.c.project_id == ids["project"]
                )
            ).scalars()
        )
    assert docs
    decision = docs[0]
    assert decision["authorization_context"] == "unverified"
    assert "cross_tenant_with_ownership" not in decision["rule_hits"]
    assert decision["executed"] is False
    if not decision["inference_ran"]:
        assert decision["top_actions"] is None
        assert decision["q_margin"] is None
        assert decision["observation"] is None
        assert decision["inference_status"] in {
            "skipped_quiet_window",
            "skipped_authorization",
            "skipped_unavailable",
        }


def test_cross_tenant_rule_persists_without_execution(env) -> None:
    alice, _, _, ids, anon = env
    now = utcnow()
    ack = _ingest(
        anon,
        ids,
        _batch(
            now,
            10,
            principals=[{"principal": "prn_alice01", "cross_tenant": 4, "own": 6}],
        ),
    )
    assert ack.status_code == 202, ack.text
    worker.drain(kinds=["live_defense_shadow"])
    page = alice.get(f"/api/v1/projects/{ids['project']}/live-policy-decisions").json()["items"]
    assert page
    decision = page[0]
    assert "cross_tenant_with_ownership" in decision["rule_hits"]
    assert decision["enforcement"] == "NOT_EXECUTED"
    assert decision["executed"] is False
    if decision["inference_ran"]:
        assert decision["top_actions"] is not None
        assert decision["checkpoint_sha256"]
    else:
        assert decision["producer"] in {"rules", "abstention"}
        assert decision["top_actions"] is None


def test_analyst_accept_on_live_decision_does_not_execute_or_label(env) -> None:
    alice, bob, outsider, ids, anon = env
    now = utcnow()
    assert _ingest(anon, ids, _batch(now, 20, e4=18, auth=18)).status_code == 202
    worker.drain(kinds=["live_defense_shadow"])
    decision = alice.get(f"/api/v1/projects/{ids['project']}/live-policy-decisions").json()[
        "items"
    ][0]
    with transaction() as conn:
        before = conn.execute(sa.select(sa.func.count()).select_from(jobs)).scalar()
    accepted = alice.post(
        f"/api/v1/live-policy-decisions/{decision['id']}/reviews",
        json={"decision": "accept", "reason": "Shadow opinion only."},
    )
    assert accepted.status_code == 201, accepted.text
    review = accepted.json()
    assert review["executes"] is False
    assert review["enforcement"] == "none"
    assert review["live_policy_decision_id"] == decision["id"]
    assert review["recommendation_id"] is None
    bob.post(
        f"/api/v1/live-policy-decisions/{decision['id']}/reviews",
        json={"decision": "reject"},
    )
    history = alice.get(f"/api/v1/live-policy-decisions/{decision['id']}/reviews").json()["items"]
    assert {item["decision"] for item in history} == {"accept", "reject"}
    with transaction() as conn:
        after = conn.execute(sa.select(sa.func.count()).select_from(jobs)).scalar()
    assert after == before
    assert (
        outsider.post(
            f"/api/v1/live-policy-decisions/{decision['id']}/reviews",
            json={"decision": "accept"},
        ).status_code
        == 404
    )


def test_live_policy_decision_cursor_and_auth(env) -> None:
    alice, _, outsider, ids, _ = env
    pid = ids["project"]
    now = utcnow()
    from shared import examples

    base = examples.build()["LivePolicyDecision"].model_dump(mode="json")
    ids_made = []
    with transaction() as conn:
        for i in range(3):
            did = new_id(IdPrefix.lpd)
            ids_made.append(did)
            end = now - timedelta(minutes=i)
            conn.execute(
                sa.insert(live_policy_decisions).values(
                    id=did,
                    project_id=pid,
                    application_id=ids["app"],
                    window_end=end,
                    source="owned_staging",
                    producer="rules",
                    inference_ran=False,
                    dedupe_key=f"{pid}:page:{i}",
                    doc={
                        **base,
                        "id": did,
                        "project_id": pid,
                        "application_id": ids["app"],
                        "window_end": end.isoformat(),
                        "created_at": end.isoformat(),
                    },
                )
            )
    page = alice.get(f"/api/v1/projects/{pid}/live-policy-decisions", params={"limit": 2}).json()
    assert len(page["items"]) == 2
    assert page["next_cursor"]
    rest = alice.get(
        f"/api/v1/projects/{pid}/live-policy-decisions",
        params={"limit": 2, "cursor": page["next_cursor"]},
    ).json()
    assert rest["items"]
    assert {item["id"] for item in page["items"]} & {item["id"] for item in rest["items"]} == set()
    assert outsider.get(f"/api/v1/live-policy-decisions/{ids_made[0]}").status_code == 404
    got = alice.get(f"/api/v1/live-policy-decisions/{ids_made[0]}")
    assert got.status_code == 200
    assert got.json()["enforcement"] == "NOT_EXECUTED"


def test_payments_lite_ground_truth_replay(env) -> None:
    alice, _, _, ids, anon = env
    fixture = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "examples/payments-lite/live_defense_shadow/ground_truth.json"
        ).read_text()
    )
    now = utcnow()
    for window in fixture["windows"]:
        end = now + timedelta(seconds=int(window["offset_s"]))
        body = {
            "source": "owned_staging",
            "window_start": (end - timedelta(minutes=1)).isoformat(),
            "window_end": end.isoformat(),
            "routes": window["routes"],
        }
        ack = _ingest(anon, ids, body)
        assert ack.status_code == 202, ack.text
    worker.drain(kinds=["live_defense_shadow"])
    items = alice.get(f"/api/v1/projects/{ids['project']}/live-policy-decisions").json()["items"]
    assert len(items) >= 3
    by_offset = {w["id"]: w["expect"] for w in fixture["windows"]}
    authz = [d for d in items if "cross_tenant_with_ownership" in d["rule_hits"]]
    assert authz, items
    assert (
        authz[0]["authorization_context"]
        == by_offset["cross_tenant_owned"]["authorization_context"]
    )
    assert all(d["executed"] is False and d["enforcement"] == "NOT_EXECUTED" for d in items)
    assert all(d["simulated"] is False for d in items)
    benign = [
        d
        for d in items
        if "cross_tenant_with_ownership" not in d["rule_hits"] and not d["rule_hits"]
    ]
    assert benign
    assert all(d["producer"] in by_offset["benign"]["producer"] for d in benign)


def test_duplicate_window_persists_one_shadow_decision(env) -> None:
    alice, _, _, ids, anon = env
    now = utcnow().replace(microsecond=0)
    body = _batch(now, 20, e4=18, auth=18)
    assert _ingest(anon, ids, body).status_code == 202
    assert _ingest(anon, ids, body).status_code == 202
    worker.drain(kinds=["live_defense_shadow"])
    items = alice.get(f"/api/v1/projects/{ids['project']}/live-policy-decisions").json()["items"]
    matching = [d for d in items if d["window_end"].startswith(now.isoformat()[:19])]
    assert len(matching) == 1


def test_replay_source_is_labelled_simulated_and_skips_shadow(env) -> None:
    alice, _, _, ids, anon = env
    project_token = alice.post(f"/api/v1/projects/{ids['project']}/ingest-tokens").json()["token"]
    now = utcnow()
    r = anon.post(
        f"/api/v1/ingest/runtime/{ids['project']}",
        json=_batch(now, 20, e4=18, auth=18, source="replay"),
        headers={"Authorization": f"Bearer {project_token}"},
    )
    assert r.status_code == 202, r.text
    worker.drain(kinds=["live_defense_shadow"])
    events = alice.get(f"/api/v1/projects/{ids['project']}/events").json()["items"]
    replay_events = [e for e in events if "replay" in (e.get("status_reason") or "").lower()]
    assert replay_events
    assert all(e["simulated"] is True for e in replay_events)
    items = alice.get(f"/api/v1/projects/{ids['project']}/live-policy-decisions").json()["items"]
    assert items == []


def test_incident_from_owned_staging_events_is_not_labelled_replay(env) -> None:
    alice, _, _, ids, anon = env
    now = utcnow()
    assert _ingest(anon, ids, _batch(now, 20, e4=18, auth=18)).status_code == 202
    worker.drain(kinds=["live_defense_shadow"])
    events = alice.get(f"/api/v1/projects/{ids['project']}/events").json()["items"]
    assert events
    assert all(item["simulated"] is False for item in events)
    created = alice.post(
        f"/api/v1/projects/{ids['project']}/incidents",
        json={
            "title": "Owned staging spike",
            "note": "Opened from authenticated owned_staging counters only.",
            "monitoring_event_ids": [events[0]["id"]],
        },
    )
    assert created.status_code == 201, created.text
    incident = created.json()
    assert incident["simulated"] is False


def test_no_browser_callable_enforcement_routes() -> None:
    from backend.main import app

    post_paths = [p.lower() for p, ops in app.openapi()["paths"].items() if "post" in ops]
    forbidden = ("/apply", "/isolate", "/rate-limit", "/block-source", "/block_source")
    for path in post_paths:
        for token in forbidden:
            assert token not in path, path


def test_same_window_from_two_applications_is_not_a_replay(env) -> None:
    alice, _, _, ids, anon = env
    app2 = alice.post(
        f"/api/v1/projects/{ids['project']}/applications",
        json={"name": "second staging", "environment": "owned_test"},
    ).json()
    token2 = alice.post(f"/api/v1/applications/{app2['id']}/ingest-tokens").json()["token"]
    end = utcnow().replace(second=0, microsecond=0)
    body = _batch(end, 20, e4=18, auth=18)
    assert _ingest(anon, ids, body).status_code == 202
    second = anon.post(
        f"/api/v1/ingest/runtime/{ids['project']}",
        json=body,
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert second.status_code == 202, second.text
    with transaction() as conn:
        from backend.db import runtime_windows

        apps = conn.execute(sa.select(runtime_windows.c.application_id)).scalars().all()
    assert sorted(apps) == sorted([ids["app"], app2["id"]])
    # A real replay by the same application is still idempotent.
    assert _ingest(anon, ids, body).status_code == 202
    with transaction() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(runtime_windows)).scalar() == 2
    worker.drain(kinds=["live_defense_shadow"])
    with transaction() as conn:
        ev = conn.execute(
            sa.select(live_policy_decisions.c.application_id, live_policy_decisions.c.doc)
        ).all()
    by_app = {r.application_id: r.doc["evidence_event_ids"] for r in ev}
    assert set(by_app) == {ids["app"], app2["id"]}
    assert by_app[ids["app"]] and by_app[app2["id"]]
    assert not set(by_app[ids["app"]]) & set(by_app[app2["id"]])


def test_pilot_trail_keeps_runtime_ingest_events(env) -> None:
    alice, _, _, ids, anon = env
    assert _ingest(anon, ids, _batch(utcnow(), 20, e4=18, auth=18)).status_code == 202
    report = alice.get(f"/api/v1/projects/{ids['project']}/pilot-report").json()
    assert "runtime.ingested" in [e["action"] for e in report["investigation_trail"]]
