"""Runtime signal ingestion against real PostgreSQL: token auth, validation, scoring,
labeled anomaly events, idempotent replay, finding linkage, RL signal feed.
All windows here are SIMULATED fixtures (source="simulated")."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from helpers import setup_project

from backend.db import ingest_tokens, transaction
from backend.host import AssessmentHost
from shared.base import utcnow
from shared.evidence import EvidenceKind, EvidenceRef, SourceSpan
from shared.findings import Finding, FindingKind, FindingStatus
from shared.ids import IdPrefix, new_id

ROUTE = "GET /payments/{payment_id}"


def _batch(
    end: datetime, requests: int, e4: int = 0, auth: int = 0, source: str = "simulated"
) -> dict:
    return {
        "source": source,
        "window_start": (end - timedelta(minutes=1)).isoformat(),
        "window_end": end.isoformat(),
        "routes": [{"route": ROUTE, "requests": requests, "status_4xx": e4, "auth_failures": auth}],
    }


@pytest.fixture
def env(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    r = alice.post(f"/api/v1/projects/{ids['project']}/ingest-tokens")
    assert r.status_code == 201, r.text
    ids["token"], ids["token_id"] = r.json()["token"], r.json()["id"]
    return alice, bob, ids, client_factory()


def _post(client, project_id: str, token: str, body: dict | str):
    kw = {"content": body} if isinstance(body, str) else {"json": body}
    return client.post(
        f"/api/v1/ingest/runtime/{project_id}", headers={"Authorization": f"Bearer {token}"}, **kw
    )


def test_token_is_shown_once_and_hashed(env) -> None:
    _, _, ids, _ = env
    with transaction() as conn:
        stored = conn.execute(sa.select(ingest_tokens.c.token_sha256)).scalars().all()
    assert ids["token"] not in stored and len(stored[0]) == 64


def test_auth_and_validation(env, client_factory) -> None:
    alice, bob, ids, anon = env
    now = utcnow()
    assert (
        anon.post(f"/api/v1/ingest/runtime/{ids['project']}", json=_batch(now, 10)).status_code
        == 401
    )
    assert _post(anon, ids["project"], "hkt_ing_wrong", _batch(now, 10)).status_code == 401
    other = alice.post("/api/v1/projects", json={"name": "other"}).json()["id"]
    assert _post(anon, other, ids["token"], _batch(now, 10)).status_code == 401, (
        "token is project-bound"
    )
    assert (
        _post(
            anon, ids["project"], ids["token"], {**_batch(now, 10), "source": "production"}
        ).status_code
        == 422
    )
    bad = _batch(now, 5, e4=9)
    r = _post(anon, ids["project"], ids["token"], bad)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_FAILED"
    assert _post(anon, ids["project"], ids["token"], "x" * 300_000).status_code == 413
    vic = client_factory("vic")
    assert vic.post(f"/api/v1/projects/{ids['project']}/ingest-tokens").status_code == 404
    assert alice.post(f"/api/v1/ingest-tokens/{ids['token_id']}/revoke").status_code == 204
    assert _post(anon, ids["project"], ids["token"], _batch(now, 10)).status_code == 401


@pytest.mark.parametrize("source", ["simulated", "runtime_demo"])
def test_spike_creates_labeled_event_linked_to_open_finding(env, source) -> None:
    alice, _, ids, anon = env
    asm = alice.post(
        f"/api/v1/projects/{ids['project']}/assessments",
        json={"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": "b" * 40},
    ).json()["assessment"]
    now = utcnow()
    fid = new_id(IdPrefix.fnd)
    AssessmentHost(asm["id"]).record_finding(
        Finding(
            id=fid,
            assessment_id=asm["id"],
            commit_sha="b" * 40,
            kind=FindingKind.security,
            title="IDOR",
            status=FindingStatus.validated,
            subject_refs=[ROUTE],
            confidence=0.9,
            created_at=now,
            updated_at=now,
            evidence=[
                EvidenceRef(
                    kind=EvidenceKind.source_span,
                    path="payments_lite/app.py",
                    commit_sha="b" * 40,
                    span=SourceSpan(start_line=1, end_line=2),
                    provenance="test",
                )
            ],
        ),
        actor="test",
    )
    base = now.replace(second=0, microsecond=0, tzinfo=UTC) - timedelta(minutes=10)
    for i, n in enumerate([100, 104, 97, 101]):
        r = _post(
            anon,
            ids["project"],
            ids["token"],
            _batch(base + timedelta(minutes=i + 1), n, e4=2, source=source),
        )
        assert r.status_code == 202 and r.json()["anomalies"] == 0, r.text
    spike_end = base + timedelta(minutes=6)
    r = _post(
        anon, ids["project"], ids["token"], _batch(spike_end, 950, e4=420, auth=400, source=source)
    )
    body = r.json()
    assert body["anomalies"] == 1 and body["scores"][0]["alert_rate"] == 3
    assert body["scores"][0]["history_windows"] == 4
    replay = _post(
        anon, ids["project"], ids["token"], _batch(spike_end, 950, e4=420, auth=400, source=source)
    ).json()
    assert replay["anomalies"] == 0 and replay["scores"][0] == body["scores"][0], (
        "replay is idempotent"
    )
    events = alice.get(f"/api/v1/projects/{ids['project']}/events").json()["items"]
    anomalies = [e for e in events if e["type"] == "log_anomaly"]
    assert len(anomalies) == 1
    ev = anomalies[0]
    assert (
        ev["source"] == "runtime"
        and ev["simulated"] is (source != "runtime_demo")
        and ev["status_reason"].startswith(f"[{source}]")
    )
    assert fid in ev["status_reason"]
    incidents = alice.get(f"/api/v1/projects/{ids['project']}/incidents").json()["items"]
    assert len(incidents) == 1
    assert incidents[0]["simulated"] is True
    assert incidents[0]["state"] == "reported"
    assert incidents[0]["triage"] is None
    assert incidents[0]["finding_ids"] == [fid]
    assert incidents[0]["monitoring_event_ids"] == [ev["id"]]

    assert alice.get(f"/api/v1/projects/{ids['project']}/reassessments").json()["items"] == [], (
        "runtime anomalies never start assessments by themselves"
    )


def test_signals_feed_rl_facts(env, settings_override) -> None:
    pm = pytest.importorskip("rl_defense.platform_mapping")
    from pathlib import Path

    import rl_defense
    from backend.pipeline import platform_facts

    _, _, ids, anon = env
    topo = (
        Path(rl_defense.__file__).resolve().parents[1]
        / "configs"
        / "topology"
        / "payments_lite.yaml"
    )
    settings_override(rl_topology_path=str(topo))
    end = utcnow().replace(microsecond=0)
    _post(anon, ids["project"], ids["token"], _batch(end, 50, e4=40, auth=35))
    with transaction() as conn:
        facts, provenance = platform_facts(conn, ids["project"])
    payments = next(n for n in facts.nodes if n.node == "payments")
    assert payments.anomaly_score > 0 and payments.alert_rate > 0
    assert any(p.startswith("signal:simulated:") for p in provenance["payments"])
    assert pm  # imported for the skip guard


# ---------------------------------------------------------------- principal counters (0.14)
def _principal_batch(
    end: datetime, source: str = "simulated", principal: str = "prn_attacker01"
) -> dict:
    return {
        "source": source,
        "window_start": (end - timedelta(minutes=1)).isoformat(),
        "window_end": end.isoformat(),
        "routes": [
            {
                "route": ROUTE,
                "requests": 8,
                "principals": [
                    {"principal": principal, "cross_tenant": 6},
                    {"principal": "prn_bookkeeper1", "delegated": 2},
                ],
            }
        ],
    }


def test_principal_counters_are_validated_stored_and_drills_excluded(env) -> None:
    from backend.api.runtime import latest_route_detections

    _, _, ids, anon = env
    end = utcnow().replace(microsecond=0)
    for bad in ("alice@example.com", "cus_alice", "prn_x"):  # raw ids / emails never accepted
        r = _post(anon, ids["project"], ids["token"], _principal_batch(end, principal=bad))
        assert r.status_code == 422, (bad, r.text)
    over = _principal_batch(end)
    over["routes"][0]["requests"] = 3
    assert _post(anon, ids["project"], ids["token"], over).status_code == 422
    assert _post(anon, ids["project"], ids["token"], _principal_batch(end)).status_code == 202
    assert (
        _post(
            anon, ids["project"], ids["token"], _principal_batch(end, "drill", "prn_drillonly1")
        ).status_code
        == 202
    )
    with transaction() as conn:
        det = latest_route_detections(conn, ids["project"])
    assert len(det) == 1 and det[0]["source"] == "simulated" and det[0]["requests"] == 8
    assert {p["principal"] for p in det[0]["principals"]} == {"prn_attacker01", "prn_bookkeeper1"}
    # a reporter without principal detection contributes no detections
    _post(anon, ids["project"], ids["token"], _batch(end + timedelta(seconds=5), 9))
    with transaction() as conn:
        assert latest_route_detections(conn, ids["project"]) == []
