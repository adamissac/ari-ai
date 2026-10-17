"""Attack drill: Claude (scripted transport here) plans a simulated attack on the project's
real routes; the drill's synthetic counters go through the real runtime ingest and scorer.
All traffic is SIMULATED (source="simulated"); nothing is executed."""

from __future__ import annotations

import json

import sqlalchemy as sa
from helpers import setup_project

from backend import llm, worker
from backend.db import monitoring_events, transaction
from backend.simulated_attack import scripted_plan


def _start(client, pid: str) -> dict:
    r = client.post(f"/api/v1/projects/{pid}/attack-drills")
    assert r.status_code == 202, r.text
    worker.drain(kinds=["attack_drill"])
    job = client.get(f"/api/v1/jobs/{r.json()['job_id']}").json()
    assert job["status"] == "succeeded", job
    return job["result"]


def test_claude_plans_and_the_real_pipeline_detects(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    plan = {
        "route": "POST /login",
        "technique": "credential_stuffing",
        "attacker": "Botnet with a leaked password list",
        "objective": "Take over reused accounts",
        "narrative": "Replays leaked credentials against sign-in.",
        "steps": ["Load list", "Rotate IPs", "Replay"],
    }
    llm.TRANSPORT_OVERRIDE = lambda: llm.FakeTransport(
        [{"content": [{"type": "text", "text": json.dumps(plan)}]}]
    )
    result = _start(alice, ids["project"])
    assert result["simulated"] is True and result["plan_author"] == "claude"
    assert result["plan"]["route"] == "POST /login"
    assert result["detection"]["detected"] is True
    assert result["response"]["executed"] is False and result["response"]["actions"]
    with transaction() as conn:
        docs = conn.execute(sa.select(monitoring_events.c.doc)).scalars().all()
    events = [d for d in docs if d["id"] in result["detection"]["monitoring_event_ids"]]
    assert events and all(e["simulated"] and e["type"] == "log_anomaly" for e in events)


def test_unusable_model_output_falls_back_to_a_scripted_plan(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    bad = {
        "route": "GET /not-a-real-route",
        "technique": "enumeration",
        "attacker": "x",
        "objective": "x",
        "narrative": "x",
        "steps": ["x"],
    }
    llm.TRANSPORT_OVERRIDE = lambda: llm.FakeTransport(
        [{"content": [{"type": "text", "text": json.dumps(bad)}]}]
    )
    result = _start(alice, ids["project"])
    assert result["plan_author"] == "scripted"
    assert result["plan"]["route"] != "GET /not-a-real-route"
    assert result["detection"]["detected"] is True


def test_non_members_cannot_start_a_drill(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    assert (
        client_factory("mallory")
        .post(f"/api/v1/projects/{ids['project']}/attack-drills")
        .status_code
        == 404
    )


def test_scripted_plan_prefers_parameterised_routes() -> None:
    plan = scripted_plan(["POST /login", "GET /invoices/{invoice_id}"], "seed")
    assert plan.route == "GET /invoices/{invoice_id}" and plan.technique == "enumeration"
