"""Tier 2: signed GitHub webhook -> persisted delivery -> durable job -> monitoring event
-> trigger policy -> reassessment request / assessment. Signed payloads are local
fixtures (simulated deliveries), not real GitHub traffic."""

from __future__ import annotations

import json

import sqlalchemy as sa
from helpers import HEAD, post_webhook, push_payload, setup_project

from backend import worker
from backend.artifacts import ArtifactStore
from backend.db import transaction, webhook_deliveries


def _process() -> list[str]:
    return worker.drain(kinds=["process_github_delivery"])


def test_signature_checks(client_factory) -> None:
    c = client_factory()
    payload = push_payload(["app/invoices.py"])
    r = post_webhook(c, payload, signature="sha256=" + "0" * 64)
    assert r.status_code == 401 and r.json()["error"]["code"] == "WEBHOOK_SIGNATURE_INVALID"
    assert post_webhook(c, payload, signature="").status_code == 401
    assert post_webhook(c, payload, secret="wrong-secret").status_code == 401
    raw = json.dumps(payload).encode()
    from conftest import WEBHOOK_SECRET

    from backend.github import sign

    sig = sign(WEBHOOK_SECRET.encode(), raw)
    tampered = raw.replace(b"invoices", b"invoicez")
    r = c.post(
        "/api/v1/webhooks/github",
        content=tampered,
        headers={
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "d-tampered-1",
            "X-Hub-Signature-256": sig,
        },
    )
    assert r.status_code == 401, "signature must cover the exact raw body"
    with transaction() as conn:
        assert (
            conn.execute(sa.select(sa.func.count()).select_from(webhook_deliveries)).scalar() == 0
        )


def test_size_limit_and_bad_headers(client_factory, settings_override) -> None:
    settings_override(webhook_max_bytes="2048")
    c = client_factory()
    big = push_payload(["x/" + "a" * 100 + f"{i}.py" for i in range(50)])
    assert post_webhook(c, big).status_code == 413
    r = post_webhook(c, push_payload(["a.py"]), delivery="bad id with spaces")
    assert r.status_code == 400


def test_valid_delivery_accepted_once_and_deduped(client_factory) -> None:
    c = client_factory()
    payload = push_payload(["app/invoices.py"])
    r1 = post_webhook(c, payload, delivery="11111111-aaaa-bbbb-cccc-000000000001")
    assert (
        r1.status_code == 202 and r1.json()["accepted"] and r1.json()["job_id"].startswith("job_")
    )
    r2 = post_webhook(c, payload, delivery="11111111-aaaa-bbbb-cccc-000000000001")
    assert (
        r2.status_code == 200
        and r2.json()["duplicate"]
        and r2.json()["job_id"] == r1.json()["job_id"]
    )
    with transaction() as conn:
        row = conn.execute(sa.select(webhook_deliveries)).mappings().one()
        _, stored = ArtifactStore().get(conn, row["payload_artifact_id"])
    assert b"ghp_" not in stored and b"REDACTED" in stored, (
        "secrets in payloads are redacted at rest"
    )


def test_push_to_connected_repo_creates_monitoring_assessment(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    post_webhook(alice, push_payload(["app/invoices.py", "tests/test_invoices.py"]))
    assert len(_process()) == 1
    events = alice.get(f"/api/v1/projects/{ids['project']}/events").json()["items"]
    assert len(events) == 1
    ev = events[0]
    assert ev["status"] == "processed" and ev["commit_range"]["head_sha"] == HEAD
    assert ev["impact"]["resolution"] == "path_only" and "code_intelligence" in ev["status_reason"]
    rrqs = alice.get(f"/api/v1/projects/{ids['project']}/reassessments").json()["items"]
    assert rrqs[0]["status"] == "started" and rrqs[0]["scope"] == "targeted"
    assert rrqs[0]["targets"] == ["app/invoices.py"]
    asm = alice.get(f"/api/v1/assessments/{rrqs[0]['assessment_id']}").json()["assessment"]
    assert (
        asm["trigger"] == "monitoring" and asm["commit_sha"] == HEAD and asm["created_by"] is None
    )
    assert asm["budget"]["max_usd"] == 3.0  # lower monitoring budget
    # Replaying the same job does not duplicate side effects.
    from backend.db import jobs as jobs_t

    with transaction() as conn:
        conn.execute(
            sa.update(jobs_t)
            .where(jobs_t.c.kind == "process_github_delivery")
            .values(status="queued", run_after=sa.func.now())
        )
    _process()
    assert len(alice.get(f"/api/v1/projects/{ids['project']}/reassessments").json()["items"]) == 1


def test_assessment_run_fails_honestly_without_orchestrator(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    post_webhook(alice, push_payload(["app/invoices.py"]))
    _process()
    worker.drain(kinds=["run_assessment"])
    asm_id = alice.get(f"/api/v1/projects/{ids['project']}/reassessments").json()["items"][0][
        "assessment_id"
    ]
    detail = alice.get(f"/api/v1/assessments/{asm_id}").json()
    a = detail["assessment"]
    # no orchestrator installed -> SUBSYSTEM_UNAVAILABLE; installed but no trusted checkout
    # bound for this repo -> SNAPSHOT_NOT_READY. Either way nothing runs or is invented.
    assert a["state"] == "FAILED"
    assert a["error"]["code"] in ("SUBSYSTEM_UNAVAILABLE", "SNAPSHOT_NOT_READY")
    assert (
        "security_agents" in a["error"]["message"]
        or "REPOSITORY_BINDINGS_FILE" in a["error"]["message"]
    )
    assert detail["agent_runs"] == [] and detail["findings"] == []  # nothing fabricated
    log = alice.get(f"/api/v1/assessments/{asm_id}/events/log").json()["items"]
    assert [e["state"] for e in log if e["type"] == "assessment.state_changed"] == [
        "CREATED",
        "SCOPE_CHECK",
        "FAILED",
    ]
    assert log[-1]["type"] == "assessment.failed"
    assert [e["seq"] for e in log] == list(range(1, len(log) + 1))


def test_policy_outcomes(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=False)
    # No active scope: blocked, nothing runs.
    post_webhook(alice, push_payload(["app/invoices.py"]))
    _process()
    rrqs = alice.get(f"/api/v1/projects/{ids['project']}/reassessments").json()["items"]
    assert rrqs[0]["status"] == "blocked_no_scope" and rrqs[0]["assessment_id"] is None
    bob.post(f"/api/v1/scopes/{ids['scope']}/approve")
    # Tests/docs only: recorded, no reassessment.
    post_webhook(alice, push_payload(["tests/test_x.py", "docs/a.md"], head="c" * 40))
    _process()
    ev = alice.get(f"/api/v1/projects/{ids['project']}/events").json()["items"][0]
    assert ev["status"] == "ignored" and "tests/docs" in ev["status_reason"]
    # Two code pushes back to back: second is coalesced (open monitoring assessment).
    post_webhook(alice, push_payload(["app/a.py"], head="d" * 40))
    post_webhook(alice, push_payload(["app/b.py"], head="e" * 40))
    _process()
    statuses = [
        r["status"]
        for r in alice.get(f"/api/v1/projects/{ids['project']}/reassessments").json()["items"]
    ]
    assert statuses.count("started") == 1 and statuses.count("coalesced") == 1


def test_unknown_repo_and_ping_are_ignored(client_factory) -> None:
    c = client_factory()
    post_webhook(c, push_payload(["a.py"], repo="someone/else"))
    post_webhook(
        c,
        {"zen": "Keep it simple", "repository": {"full_name": "acme/payments-lite"}},
        event="ping",
    )
    from backend.db import jobs as jobs_t

    _process()
    with transaction() as conn:
        results = [r for r in conn.execute(sa.select(jobs_t.c.result)).scalars()]
    assert {"ignored": "repository someone/else is not connected"} in results
    assert {"ignored": "ping"} in results


def test_a_burst_of_signed_deliveries_is_never_rejected(client_factory):
    """GitHub does not retry a 429, so a rate limit here would silently lose commits."""
    from helpers import post_webhook, push_payload

    c = client_factory()
    payload = push_payload(["app.py"])
    codes = {post_webhook(c, payload).status_code for _ in range(150)}
    assert codes == {202}
