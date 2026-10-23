"""Live Defense Phase 6: post-merge shadow vs enforcement integration audit.

Proves the recommendation-only shadow path cannot execute even when owned-test
grants, channels, v6/rules producers, analyst accept, worker retries, and the
pilot report are present. Owned-test execute remains a separate POST.
"""

from __future__ import annotations

import hashlib
import socket
from datetime import timedelta

import pytest
import sqlalchemy as sa
from helpers import setup_project

from backend import jobs as jobq
from backend import worker
from backend.db import ingest_tokens, jobs, live_controls, live_policy_decisions, transaction
from backend.live_defense.owned_test_app import create_app, serve_in_thread
from backend.live_defense.policy import decide_inference
from monitoring.detect import WindowView, detect
from shared.base import utcnow
from shared.live_defense import PILOT_UNSUPPORTED_CLAIMS, AuthorizationContext, InferenceStatus
from shared.monitoring import PrincipalCounts

ROUTE = "GET /payments/{payment_id}"
ALL_LIVE_KINDS = [
    "live_defense_shadow",
    "live_defense_execute",
    "live_defense_verify",
    "live_defense_rollback",
    "live_defense_expire",
    "live_defense_emergency_stop",
]


def _batch(end, requests: int = 20, e4: int = 18, auth: int = 18, principals=None) -> dict:
    route = {
        "route": ROUTE,
        "requests": requests,
        "status_4xx": e4,
        "auth_failures": auth,
    }
    if principals is not None:
        route["principals"] = principals
    return {
        "source": "owned_staging",
        "window_start": (end - timedelta(minutes=1)).isoformat(),
        "window_end": end.isoformat(),
        "routes": [route],
    }


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _job_rows(project_id: str | None = None):
    with transaction() as conn:
        stmt = sa.select(jobs)
        if project_id is not None:
            stmt = stmt.where(jobs.c.payload["project_id"].astext == project_id)
        return conn.execute(stmt).mappings().all()


def _control_count(project_id: str) -> int:
    with transaction() as conn:
        return int(
            conn.execute(
                sa.select(sa.func.count())
                .select_from(live_controls)
                .where(live_controls.c.project_id == project_id)
            ).scalar()
            or 0
        )


def _decision_count(project_id: str) -> int:
    with transaction() as conn:
        return int(
            conn.execute(
                sa.select(sa.func.count())
                .select_from(live_policy_decisions)
                .where(live_policy_decisions.c.project_id == project_id)
            ).scalar()
            or 0
        )


@pytest.fixture
def env(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    outsider = client_factory("mallory")
    other = outsider.post("/api/v1/projects", json={"name": "other-org"})
    assert other.status_code == 201, other.text
    ids["outsider_project"] = other.json()["id"]
    app = alice.post(
        f"/api/v1/projects/{ids['project']}/applications",
        json={"name": "payments-lite staging", "environment": "owned_test"},
    ).json()
    assert app["shadow_mode"] is True
    token = alice.post(f"/api/v1/applications/{app['id']}/ingest-tokens").json()["token"]
    ids["app"] = app["id"]
    ids["token"] = token
    return alice, bob, outsider, ids, client_factory()


@pytest.fixture
def fixture_server():
    secret = "hkt_ctl_phase6_not_a_real_key"
    app = create_app(secret)
    port, stop = serve_in_thread(app)
    yield {"port": port, "secret": secret, "app": app}
    stop()


def _grant_and_channel(alice, ids, port: int) -> dict:
    grant = alice.post(
        f"/api/v1/projects/{ids['project']}/control-grants",
        json={
            "application_id": ids["app"],
            "allowed_kinds": ["rate_limit", "block_source", "increase_logging", "escalate"],
            "max_duration_s": 300,
            "hourly_budget": 10,
        },
    )
    assert grant.status_code == 201, grant.text
    channel = alice.post(
        f"/api/v1/applications/{ids['app']}/control-channel",
        json={"port": port},
    )
    assert channel.status_code == 201, channel.text
    return channel.json()


def test_shadow_path_does_not_execute_with_grant_channel_v6_rules_accept_retries_report(
    env,
) -> None:
    alice, bob, outsider, ids, anon = env
    pid = ids["project"]
    port = _free_port()
    created = _grant_and_channel(alice, ids, port)
    fixture = create_app(created["hmac_secret"])
    plane = fixture.state.plane
    bound, stop = serve_in_thread(fixture, port=port)
    assert bound == port
    try:
        now = utcnow()
        spike = anon.post(
            f"/api/v1/ingest/runtime/{pid}",
            json=_batch(
                now,
                principals=[{"principal": "prn_alice01", "cross_tenant": 4, "own": 6}],
            ),
            headers={"Authorization": f"Bearer {ids['token']}"},
        )
        assert spike.status_code == 202, spike.text
        assert spike.json()["anomalies"] >= 1
        events = alice.get(f"/api/v1/projects/{pid}/events").json()["items"]
        assert events

        drained = worker.drain(max_jobs=30, kinds=ALL_LIVE_KINDS)
        assert drained
        page = alice.get(f"/api/v1/projects/{pid}/live-policy-decisions").json()["items"]
        assert page
        decision = page[0]
        assert decision["enforcement"] == "NOT_EXECUTED"
        assert decision["executed"] is False
        assert decision["producer"] in {"rules", "v6_shadow", "abstention"}
        if decision["inference_ran"]:
            assert decision["top_actions"] is not None
            assert decision["checkpoint_sha256"]
        else:
            assert decision["top_actions"] is None
            assert decision["q_margin"] is None
            assert decision["observation"] is None

        before_controls = _control_count(pid)
        assert before_controls == 0
        accept = alice.post(
            f"/api/v1/live-policy-decisions/{decision['id']}/reviews",
            json={"decision": "accept", "reason": "Shadow opinion only."},
        )
        assert accept.status_code == 201, accept.text
        assert accept.json()["executes"] is False
        assert accept.json()["enforcement"] == "none"
        bob.post(
            f"/api/v1/live-policy-decisions/{decision['id']}/reviews",
            json={"decision": "needs_investigation"},
        )

        with transaction() as conn:
            jobq.enqueue(
                conn,
                "live_defense_shadow",
                {
                    "project_id": pid,
                    "application_id": ids["app"],
                    "window_end": now.isoformat(),
                    "source": "owned_staging",
                },
                dedupe_key=f"phase6-retry-shadow:{pid}:{now.isoformat()}",
            )
        worker.drain(max_jobs=30, kinds=ALL_LIVE_KINDS)
        assert _decision_count(pid) == 1
        assert _control_count(pid) == 0
        assert plane.controls == {}

        health = alice.get(f"/api/v1/projects/{pid}/defense-health").json()
        assert health["status"] == "unknown"
        assert health["worker_status"] == "unknown"
        assert health["telemetry_status"] == "unknown"
        assert health["policy_status"] == "unknown"
        assert health["last_ingest_at"] is not None
        graph = alice.get(f"/api/v1/projects/{pid}/defense-graph").json()
        assert "healthy" not in {obs["state"] for obs in graph["observations"]}

        report = alice.get(f"/api/v1/projects/{pid}/pilot-report")
        assert report.status_code == 200, report.text
        body = report.json()
        assert body["shadow_mode"] is True
        assert body["shadow_decisions"] == 1
        assert body["reviews"] >= 1
        assert body["health"]["status"] == "unknown"
        for claim in PILOT_UNSUPPORTED_CLAIMS:
            assert claim in body["unsupported_claims"]
        assert (
            "apply" not in report.text.lower()
            or "does not execute" in " ".join(body["caveats"]).lower()
        )

        kinds = {row["kind"] for row in _job_rows(pid)}
        assert "live_defense_shadow" in kinds
        assert "live_defense_execute" not in kinds
        assert outsider.get(f"/api/v1/projects/{pid}/pilot-report").status_code == 404
        assert outsider.get(f"/api/v1/projects/{pid}/live-policy-decisions").status_code == 404
    finally:
        stop()


def test_disconnected_app_cannot_authorize_or_execute_leftover_grant(env, fixture_server) -> None:
    alice, _, _, ids, _ = env
    _grant_and_channel(alice, ids, fixture_server["port"])
    stopped = alice.post(f"/api/v1/applications/{ids['app']}/disconnect")
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["verification"] == "disconnected"
    res = alice.post(
        f"/api/v1/applications/{ids['app']}/control-authorizations",
        json={
            "kind": "rate_limit",
            "target": {"type": "route", "value": "GET /payments/pay_fixture"},
            "duration_s": 60,
            "max_requests": 1,
        },
    )
    assert res.status_code == 403, res.text
    assert res.json()["error"]["code"] == "LIVE_CONTROL_DENIED"
    listed = alice.get(f"/api/v1/projects/{ids['project']}/live-controls").json()["items"]
    assert listed and listed[0]["status"] in {"rejected", "escalated"}
    worker.drain(max_jobs=20, kinds=ALL_LIVE_KINDS)
    execute_jobs = [
        row for row in _job_rows(ids["project"]) if row["kind"] == "live_defense_execute"
    ]
    assert execute_jobs == []


def test_disconnect_after_authorize_blocks_execute_toctou(env) -> None:
    alice, _, _, ids, _ = env
    port = _free_port()
    created = _grant_and_channel(alice, ids, port)
    fixture = create_app(created["hmac_secret"])
    plane = fixture.state.plane
    bound, stop = serve_in_thread(fixture, port=port)
    assert bound == port
    try:
        res = alice.post(
            f"/api/v1/applications/{ids['app']}/control-authorizations",
            json={
                "kind": "rate_limit",
                "target": {"type": "route", "value": "GET /payments/pay_fixture"},
                "duration_s": 60,
                "max_requests": 1,
            },
        )
        assert res.status_code == 201, res.text
        assert res.json()["status"] == "authorized"
        stopped = alice.post(f"/api/v1/applications/{ids['app']}/disconnect")
        assert stopped.status_code == 200, stopped.text
        worker.drain(max_jobs=20, kinds=ALL_LIVE_KINDS)
        got = alice.get(f"/api/v1/live-controls/{res.json()['id']}").json()
        assert got["status"] == "rejected"
        assert plane.controls == {}
    finally:
        stop()


def test_tenant_isolation_and_credentials_are_hashes_not_secrets(env, fixture_server) -> None:
    alice, _, outsider, ids, _ = env
    pid = ids["project"]
    token = ids["token"]
    created = _grant_and_channel(alice, ids, fixture_server["port"])
    secret = created["hmac_secret"]
    listed_channel = alice.get(f"/api/v1/applications/{ids['app']}/control-channel")
    assert listed_channel.status_code == 200
    assert "hmac_secret" not in listed_channel.text
    tokens = alice.get(f"/api/v1/projects/{pid}/ingest-tokens")
    assert token not in tokens.text
    audit = alice.get(f"/api/v1/audit?project_id={pid}")
    assert audit.status_code == 200, audit.text
    assert token not in audit.text
    assert secret not in audit.text
    with transaction() as conn:
        rows = (
            conn.execute(sa.select(ingest_tokens).where(ingest_tokens.c.project_id == pid))
            .mappings()
            .all()
        )
        assert rows
        for row in rows:
            assert token not in str(dict(row))
            assert row["token_sha256"] == hashlib.sha256(token.encode()).hexdigest()
    for path in (
        f"/api/v1/projects/{pid}/applications",
        f"/api/v1/applications/{ids['app']}",
        f"/api/v1/projects/{pid}/defense-health",
        f"/api/v1/projects/{pid}/pilot-report",
        f"/api/v1/projects/{pid}/control-grants",
        f"/api/v1/projects/{pid}/live-controls",
        f"/api/v1/projects/{pid}/ingest-tokens",
        f"/api/v1/applications/{ids['app']}/control-channel",
    ):
        assert outsider.get(path).status_code == 404, path
    assert (
        outsider.post(
            f"/api/v1/applications/{ids['app']}/control-authorizations",
            json={
                "kind": "escalate",
                "target": {"type": "none", "value": ""},
                "duration_s": 60,
            },
        ).status_code
        == 404
    )


def test_worker_failure_is_visible_and_health_stays_unknown(env) -> None:
    alice, _, outsider, ids, _ = env
    pid = ids["project"]
    with transaction() as conn:
        jid, _ = jobq.enqueue(
            conn,
            "live_defense_shadow",
            {"project_id": pid},
            dedupe_key=f"phase6-poison-shadow:{pid}",
            max_attempts=1,
        )
    worker.drain(max_jobs=5, kinds=["live_defense_shadow"])
    shown = alice.get(f"/api/v1/jobs/{jid}")
    assert shown.status_code == 200, shown.text
    body = shown.json()
    assert body["kind"] == "live_defense_shadow"
    assert body["status"] in {"failed", "dead", "queued"}
    assert body["last_error"] is not None
    assert body["last_error"]["code"]
    health = alice.get(f"/api/v1/projects/{pid}/defense-health").json()
    assert health["status"] == "unknown"
    assert health["worker_status"] == "unknown"
    report = alice.get(f"/api/v1/projects/{pid}/pilot-report").json()
    assert report["health"]["status"] == "unknown"
    assert any(
        item["subject_id"] == jid and "last_error" in (item.get("detail") or "")
        for item in report["investigation_trail"]
    )
    assert outsider.get(f"/api/v1/jobs/{jid}").status_code == 404


def test_queue_depth_is_project_scoped_not_other_tenants(env) -> None:
    alice, _, _, ids, _ = env
    with transaction() as conn:
        jobq.enqueue(
            conn,
            "live_defense_shadow",
            {"project_id": ids["outsider_project"], "window_end": utcnow().isoformat()},
            dedupe_key=f"phase6-other-queue:{ids['outsider_project']}",
        )
    health = alice.get(f"/api/v1/projects/{ids['project']}/defense-health").json()
    assert health["status"] == "unknown"
    assert health["queue_depth"] == 0


def test_frozen_v6_hash_mismatch_refuses_load(tmp_path, monkeypatch) -> None:
    from backend.live_defense import policy

    bad = tmp_path / "candidate_online.pt"
    bad.write_bytes(b"not-the-frozen-v6-checkpoint")
    monkeypatch.setattr(policy, "V6_CHECKPOINT", bad)
    monkeypatch.setattr(policy, "_RUNNER", None)
    with pytest.raises(ValueError, match="hash mismatch"):
        policy._load_v6()
    window = WindowView(
        route=ROUTE,
        requests=20,
        status_4xx=18,
        status_5xx=0,
        auth_failures=18,
        principals=(PrincipalCounts(principal="prn_alice01", cross_tenant=4, own=6),),
        anomaly_score=0.9,
        source="owned_staging",
        successes=2,
    )
    hits = detect([window])
    result = decide_inference(
        source="owned_staging",
        windows=[window],
        hits=hits,
        auth=AuthorizationContext.verified,
        window_end=utcnow(),
    )
    assert result.status is InferenceStatus.skipped_unavailable
    assert result.top_actions is None
    assert result.q_margin is None
    assert result.observation is None


def test_no_browser_callable_bypass_and_shadow_routes_remain(env) -> None:
    from backend.main import app

    post_paths = [p.lower() for p, ops in app.openapi()["paths"].items() if "post" in ops]
    for path in post_paths:
        for token in ("/isolate", "/block-source", "/block_source", "/rate-limit", "/apply"):
            assert token not in path, path
    assert any("control-authorizations" in p for p in post_paths)
    assert any("live-policy-decisions" in p and p.endswith("/reviews") for p in post_paths)
    alice, _, _, ids, _ = env
    listed = alice.get(f"/api/v1/projects/{ids['project']}/live-controls").json()
    assert listed["items"] == []
