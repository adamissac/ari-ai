"""Scenarios A–H: Live Defense owned-staging end-to-end integration tests.

Drives real HTTP routes, the real database, the real durable job queue
(``worker.drain``), and the real ``security_agents`` runtime. The model is
scripted (FakeLLM / injected wrappers); every record is labelled
``provider_mode="fake"``. Nothing here validates real Anthropic execution —
the single opt-in live test at the bottom is marked ``live_llm``.

Markers: ``live_defense_e2e`` (all), ``live_defense_smoke`` (fast CI subset),
``live_defense_fault`` (failure-injection suite), ``live_llm`` (opt-in live).
"""

from __future__ import annotations

import json
import os

import pytest
from helpers import add_member

from backend import llm
from backend.live_defense import first_responder
from security_agents.contracts import AgentName as RuntimeAgentName
from shared.base import utcnow
from shared.live_defense import (
    AgentInvocationStatus,
    AnalystHandoffState,
    ConfirmationState,
    ExecutionIntegrity,
)

from .transports import (
    FailAfterCalls,
    HookProvider,
    adversarial_scout_script,
    all_role_scripts,
    fake_provider,
    gateway_factory,
)

pytest.importorskip("security_agents")

pytestmark = pytest.mark.live_defense_e2e

INV = AgentInvocationStatus


# ---------------------------------------------------------------------------
# Scenario A — successful investigation: telemetry -> decision -> Scout ->
# Diagnose -> analyst handoff, with every persisted state/artifact verified.
# ---------------------------------------------------------------------------


@pytest.mark.live_defense_smoke
def test_a_successful_investigation(staging, client_factory, report):
    alice, bob = staging.login("alice"), staging.login("bob")
    app = staging.create_project(alice, bob, approve_scope=True)
    repo, sha = staging.checkout_owned_repo("repo-a")
    staging.bind_repo(app, repo)
    staging.index_snapshot(app.repo_id, sha)
    staging.register_app(app)
    staging.issue_token(app)
    staging.attest_mapping(app, commit_sha=sha)

    assert staging.set_mode(alice, app.project_id, "assisted_response").status_code == 200
    resp = staging.ingest(alice, app)
    assert resp.status_code == 202, resp.text
    report.check("ingest accepted", 202, resp.status_code)

    staging.drain()

    decisions = staging.decisions(alice, app.project_id)
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision["action"] == "confirm_with_probe"
    assert decision["executed"] is False
    assert decision["confirmation"] == ConfirmationState.unverified.value
    assert decision["predicted_probability"] is None
    assert decision["correlation"]["commit_sha"] == sha
    assert decision["trigger_event_ids"]
    report.check("orchestrator action", "confirm_with_probe", decision["action"])

    inv = staging.by_agent(staging.invocations(alice, app.project_id))
    scout = inv["scout"]
    assert scout["status"] == INV.executed.value
    assert scout["provider_mode"] == "fake"
    ex = scout["execution"]
    assert ex["typed_output"] is True
    assert ex["execution_integrity"] == ExecutionIntegrity.checked.value
    assert ex["evidence_verified"] is False
    assert ex["confirmation"] == ConfirmationState.unverified.value
    assert ex["hypothesis_count"] >= 1
    assert ex["transcript_artifact_id"] and ex["output_artifact_id"]
    assert inv["diagnose"]["status"] == INV.executed.value
    assert inv["diagnose"]["execution"]["evidence_verified"] is False
    assert inv["fortify"]["status"] == INV.skipped_no_prerequisite.value
    assert inv["probe"]["status"] == INV.completed_unverified.value
    assert inv["patch"]["status"] == INV.skipped_no_approval.value
    report.check("scout outcome", INV.executed.value, scout["status"])

    # Artifact integrity: read back through the store (sha256 verified).
    meta, transcript = staging.artifact_json(ex["transcript_artifact_id"])
    assert meta["project_id"] == app.project_id
    assert transcript.get("turns") or transcript.get("llm_turns") is not None or len(transcript)
    report.artifact(ex["transcript_artifact_id"], meta["kind"], "scout transcript")
    _, output = staging.artifact_json(ex["output_artifact_id"])
    assert output.get("hypotheses"), "scout output artifact must carry validated hypotheses"
    report.artifact(ex["output_artifact_id"], "tool_output", "scout hypotheses")

    handoffs = staging.handoffs(alice, app.project_id)
    assert len(handoffs) == 1
    handoff = handoffs[0]
    assert handoff["state"] == AnalystHandoffState.delivery_pending.value
    assert handoff["confirmation"] == ConfirmationState.unverified.value

    hid = handoff["id"]
    ack = alice.post(
        f"/api/v1/first-responder/handoffs/{hid}/delivery-ack",
        json={
            "provider": "slack",
            "provider_message_id": "e2e-msg-1",
            "received_at": utcnow().isoformat(),
        },
    )
    assert ack.status_code == 200, ack.text
    confirm = alice.post(f"/api/v1/first-responder/handoffs/{hid}/confirm")
    assert confirm.status_code == 409, confirm.text
    report.check("handoff confirm refused without executed probe", 409, confirm.status_code)

    assert staging.table_count(staging.T.runtime_windows, app.project_id) >= 1
    assert staging.table_count(staging.T.monitoring_events, app.project_id) >= 1
    assert "live_defense.first_responder.decided" in staging.audit_actions(app.project_id)


# ---------------------------------------------------------------------------
# Scenario B — missing authorization: bad token refused, no mapping means no
# investigation, no approved scope means no Probe, RBAC enforced.
# ---------------------------------------------------------------------------


@pytest.mark.live_defense_smoke
def test_b_missing_authorization(staging, report):
    alice, bob = staging.login("alice"), staging.login("bob")
    carol, dave = staging.login("carol"), staging.login("dave")

    app = staging.create_project(alice, bob)
    repo, sha = staging.checkout_owned_repo("repo-b")
    staging.bind_repo(app, repo)
    staging.index_snapshot(app.repo_id, sha)
    staging.register_app(app)
    token = staging.issue_token(app)
    # Deliberately no deploy mapping.

    assert staging.set_mode(alice, app.project_id, "monitor").status_code == 200

    # B1 — invalid ingest token is refused; nothing is persisted or investigated.
    bad = staging.ingest(alice, app, token="hkt_bad_token")
    assert bad.status_code != 202
    report.check("invalid ingest token refused", "not 202", bad.status_code)
    assert staging.table_count(staging.T.first_responder_decisions, app.project_id) == 0

    # B2 — valid token, no deploy mapping: correlation unknown -> correlate,
    # every investigative agent is skipped_no_mapping, zero code access.
    ok = staging.ingest(alice, app, token=token)
    assert ok.status_code == 202, ok.text
    staging.drain()
    decisions = staging.decisions(alice, app.project_id)
    assert decisions and decisions[0]["action"] == "correlate"
    assert decisions[0]["correlation"]["confidence"] == "unknown"
    inv = staging.by_agent(staging.invocations(alice, app.project_id))
    for agent in ("scout", "diagnose", "fortify"):
        assert inv[agent]["status"] == INV.skipped_no_mapping.value
    assert not staging.artifact_rows(app.project_id, kind="llm_transcript")
    report.check(
        "no mapping -> scout blocked", INV.skipped_no_mapping.value, inv["scout"]["status"]
    )

    # B3 — assisted response without an approved scope: Probe is skipped_no_scope.
    app2 = staging.create_project(alice, bob, name="payments-lite-2", approve_scope=False)
    repo2, sha2 = staging.checkout_owned_repo("repo-b2")
    staging.bind_repo(app2, repo2)
    staging.index_snapshot(app2.repo_id, sha2)
    staging.register_app(app2)
    staging.issue_token(app2)
    staging.attest_mapping(app2, commit_sha=sha2)
    staging.set_mode(alice, app2.project_id, "assisted_response")
    assert staging.ingest(alice, app2).status_code == 202
    staging.drain()
    inv2 = staging.by_agent(staging.invocations(alice, app2.project_id))
    assert inv2["probe"]["status"] == INV.skipped_no_scope.value
    assert inv2["scout"]["status"] == INV.executed.value
    report.check(
        "no approved scope -> probe blocked", INV.skipped_no_scope.value, inv2["probe"]["status"]
    )

    # B4 — RBAC: non-owner member gets 403, outsider gets 404, auto-execute rejected.
    add_member(app.org_id, dave.me["user"]["id"], role="member")
    assert staging.set_mode(dave, app.project_id, "monitor").status_code == 403
    assert staging.set_mode(carol, app.project_id, "monitor").status_code == 404
    assert (
        carol.get(f"/api/v1/projects/{app.project_id}/first-responder/invocations").status_code
        == 404
    )
    bad_intent = staging.set_mode(alice, app.project_id, "auto_execute")
    assert bad_intent.status_code >= 400
    report.check("RBAC on mode API", "member 403 / outsider 404 / auto_execute 4xx", "403/404/4xx")


# ---------------------------------------------------------------------------
# Scenario C — stale snapshot: telemetry mapped to an old commit must not be
# investigated against a newer/HEAD commit.
# ---------------------------------------------------------------------------


def test_c_stale_snapshot(staging, report):
    alice, bob = staging.login("alice"), staging.login("bob")
    app = staging.create_project(alice, bob)
    repo, sha_new = staging.checkout_owned_repo(
        "repo-c", extra_commit={"target/app/extra.py": "x = 1\n"}
    )
    # Commit history is [old, new]; the deployed mapping covers the window but
    # points at the OLD commit, while only the NEWER commit was indexed.
    sha_old = staging.git(repo, "rev-parse", "HEAD~1")
    staging.bind_repo(app, repo)
    staging.register_app(app)
    staging.issue_token(app)
    # The deployed mapping covers the window but points at the OLD commit.
    staging.attest_mapping(app, commit_sha=sha_old)
    # Only the NEWER commit was ever indexed.
    staging.index_snapshot(app.repo_id, sha_new)
    staging.set_mode(alice, app.project_id, "monitor")

    assert staging.ingest(alice, app).status_code == 202
    staging.drain()
    inv = staging.by_agent(staging.invocations(alice, app.project_id))
    # Scout must NOT silently investigate the wrong commit.
    assert inv["scout"]["status"] == INV.skipped_no_snapshot.value
    assert all(i["status"] != INV.executed.value for i in inv.values())
    assert not staging.artifact_rows(app.project_id, kind="llm_transcript")
    report.check(
        "missing snapshot for mapped sha", INV.skipped_no_snapshot.value, inv["scout"]["status"]
    )

    # Once the *mapped* commit is indexed, the next window is investigated —
    # pinned to the mapped sha, not HEAD.
    staging.index_snapshot(app.repo_id, sha_old)
    assert staging.ingest(alice, app).status_code == 202
    staging.drain()
    # A second decision was recorded for the new window; its scout executed.
    decisions = staging.decisions(alice, app.project_id)
    latest = decisions[0]
    scout2 = next(
        i
        for i in staging.invocations(alice, app.project_id)
        if i["decision_id"] == latest["id"] and i["agent"] == "scout"
    )
    assert scout2["status"] == INV.executed.value
    assert latest["correlation"]["commit_sha"] == sha_old
    assert latest["correlation"]["commit_sha"] != sha_new
    report.check(
        "investigated commit == mapped commit", sha_old, decisions[0]["correlation"]["commit_sha"]
    )


# ---------------------------------------------------------------------------
# Scenario D — provider failure after some successful calls (fault injection).
# ---------------------------------------------------------------------------


@pytest.mark.live_defense_fault
def test_d_provider_failure(staging, report):
    alice, bob = staging.login("alice"), staging.login("bob")
    app = staging.create_project(alice, bob)
    repo, sha = staging.checkout_owned_repo("repo-d")
    staging.bind_repo(app, repo)
    staging.index_snapshot(app.repo_id, sha)
    staging.register_app(app)
    staging.issue_token(app)
    staging.attest_mapping(app, commit_sha=sha)
    staging.set_mode(alice, app.project_id, "monitor")

    # Scout runs fully; Diagnose gets one successful turn then the provider dies.
    flaky = FailAfterCalls(fake_provider(repo / "target"), agents={"diagnose"}, succeed=1)
    staging.use_gateway(gateway_factory(flaky))

    assert staging.ingest(alice, app).status_code == 202
    staging.drain()

    inv = staging.by_agent(staging.invocations(alice, app.project_id))
    assert inv["scout"]["status"] == INV.executed.value
    diagnose = inv["diagnose"]
    assert diagnose["status"] == INV.failed.value
    assert diagnose["execution"]["error_code"] == "LLM_UNAVAILABLE"
    # Partial evidence retained: the failed run still persisted its transcript.
    assert diagnose["execution"]["transcript_artifact_id"]
    meta, transcript = staging.artifact_json(diagnose["execution"]["transcript_artifact_id"])
    assert meta["project_id"] == app.project_id
    report.artifact(
        diagnose["execution"]["transcript_artifact_id"], meta["kind"], "diagnose partial transcript"
    )
    report.check(
        "provider failure recorded", "LLM_UNAVAILABLE", diagnose["execution"]["error_code"]
    )
    # Failure reporting is honest: not faked into a skip or a success.
    assert diagnose["execution"]["evidence_verified"] is False
    assert diagnose["execution"]["confirmation"] == "unverified"
    decisions = staging.decisions(alice, app.project_id)
    assert decisions and decisions[0]["executed"] is False


# ---------------------------------------------------------------------------
# Scenario E — worker failure mid-investigation (fault injection): crash after
# Scout's execution artifacts persist; retry must keep partial evidence and
# recover the execution state idempotently.
# ---------------------------------------------------------------------------


@pytest.mark.live_defense_fault
def test_e_worker_failure(staging, monkeypatch, report):
    alice, bob = staging.login("alice"), staging.login("bob")
    app = staging.create_project(alice, bob)
    repo, sha = staging.checkout_owned_repo("repo-e")
    staging.bind_repo(app, repo)
    staging.index_snapshot(app.repo_id, sha)
    staging.register_app(app)
    staging.issue_token(app)
    staging.attest_mapping(app, commit_sha=sha)
    staging.set_mode(alice, app.project_id, "monitor")

    calls = {"scout": 0}
    orig = first_responder.run_investigative

    def crash_after_scout_execution(**kwargs):
        result = orig(**kwargs)
        if kwargs["agent"].value == "scout" and calls["scout"] == 0:
            calls["scout"] += 1
            raise RuntimeError("simulated worker crash after scout execution persisted")
        return result

    monkeypatch.setattr(first_responder, "run_investigative", crash_after_scout_execution)

    assert staging.ingest(alice, app).status_code == 202
    staging.drain()

    # The step's artifacts persisted before the crash; the invocation is still
    # queued and the job was requeued with backoff.
    inv = staging.by_agent(staging.invocations(alice, app.project_id))
    assert inv["scout"]["status"] == INV.queued.value
    step_jobs = [j for j in staging.job_rows() if j["kind"] == "live_defense_agent_step"]
    crashed = next(
        (j for j in step_jobs if "simulated worker crash" in json.dumps(j.get("last_error") or {})),
        None,
    )
    assert crashed is not None, "expected the crashed scout job to record its error"
    report.check(
        "partial evidence retained",
        "crash recorded",
        json.dumps(crashed.get("last_error") or {})[:120],
    )

    # Recovery: make the requeued job claimable and drain again.
    staging.requeue_now(crashed["id"])
    staging.drain()

    inv = staging.by_agent(staging.invocations(alice, app.project_id))
    assert inv["scout"]["status"] == INV.executed.value
    # Both attempts' transcripts were retained — nothing was lost or deduplicated away.
    transcripts = staging.artifact_rows(app.project_id, kind="llm_transcript")
    assert len(transcripts) >= 2
    # Exactly one decision, one scout invocation — recovery did not double-execute.
    assert len(staging.decisions(alice, app.project_id)) == 1
    assert sum(1 for i in inv.values() if i["agent"] == "scout") == 1
    report.check("recovery outcome", INV.executed.value, inv["scout"]["status"])


# ---------------------------------------------------------------------------
# Scenario F — OFF-mode interruption during an active investigation (fault).
# ---------------------------------------------------------------------------


@pytest.mark.live_defense_fault
def test_f_off_mode_interruption(staging, report):
    alice, bob = staging.login("alice"), staging.login("bob")
    app = staging.create_project(alice, bob)
    repo, sha = staging.checkout_owned_repo("repo-f")
    staging.bind_repo(app, repo)
    staging.index_snapshot(app.repo_id, sha)
    staging.register_app(app)
    staging.issue_token(app)
    staging.attest_mapping(app, commit_sha=sha)
    staging.set_mode(alice, app.project_id, "monitor")

    # Flip mode OFF inside the second model call — mid-investigation.
    fake = fake_provider(repo / "target")
    hooked = HookProvider(
        fake,
        when=2,
        on_call=lambda _req: staging.set_mode(alice, app.project_id, "off"),
    )
    staging.use_gateway(gateway_factory(hooked))

    assert staging.ingest(alice, app).status_code == 202
    staging.drain()

    inv = staging.by_agent(staging.invocations(alice, app.project_id))
    assert inv["scout"]["status"] == INV.cancelled.value
    # No further agent step ran after OFF took effect.
    assert inv["diagnose"]["status"] in {INV.cancelled.value, INV.queued.value}
    assert inv["diagnose"]["status"] != INV.executed.value
    # The provider saw no calls beyond the hook point.
    assert len(fake.calls) == 2
    report.check("calls after OFF", "<=2", len(fake.calls), ok=len(fake.calls) <= 2)
    # OFF produced no execution artifacts for diagnose and no control jobs.
    assert not any(j["kind"].startswith("live_defense_execute") for j in staging.job_rows())
    mode = alice.get(f"/api/v1/projects/{app.project_id}/first-responder/mode").json()
    assert mode["intent"] == "off"
    report.check("mode effective", "off", mode["intent"])


# ---------------------------------------------------------------------------
# Scenario G — multi-project isolation: two projects' workflows stay disjoint.
# ---------------------------------------------------------------------------


def test_g_multi_project_isolation(staging, report):
    alice, bob, dave = staging.login("alice"), staging.login("bob"), staging.login("dave")
    carol = staging.login("carol")

    app1 = staging.create_project(alice, bob, name="payments-lite-1")
    repo1, sha1 = staging.checkout_owned_repo("repo-g1")
    staging.bind_repo(app1, repo1)
    staging.index_snapshot(app1.repo_id, sha1)
    staging.register_app(app1, name="staging-1")
    staging.issue_token(app1)
    staging.attest_mapping(app1, commit_sha=sha1)
    staging.set_mode(alice, app1.project_id, "monitor")

    app2 = staging.create_project(alice, dave, name="payments-lite-2")
    repo2, sha2 = staging.checkout_owned_repo(
        "repo-g2", extra_commit={"target/payments_lite/tenant.py": "TENANT = 'g2'\n"}
    )
    staging.bind_repo(app2, repo2)
    staging.index_snapshot(app2.repo_id, sha2)
    staging.register_app(app2, name="staging-2")
    staging.issue_token(app2)
    staging.attest_mapping(app2, commit_sha=sha2)
    staging.set_mode(alice, app2.project_id, "monitor")

    assert staging.ingest(alice, app1).status_code == 202
    assert staging.ingest(alice, app2).status_code == 202
    staging.drain(max_jobs=80)

    d1 = staging.decisions(alice, app1.project_id)
    d2 = staging.decisions(alice, app2.project_id)
    assert len(d1) == 1 and len(d2) == 1
    assert d1[0]["correlation"]["commit_sha"] == sha1
    assert d2[0]["correlation"]["commit_sha"] == sha2
    assert sha1 != sha2
    report.check(
        "project isolation of correlated commits", (sha1, sha2), "distinct", ok=sha1 != sha2
    )

    inv1 = staging.invocations(alice, app1.project_id)
    inv2 = staging.invocations(alice, app2.project_id)
    assert all(i["project_id"] == app1.project_id for i in inv1)
    assert all(i["project_id"] == app2.project_id for i in inv2)
    assert {i["id"] for i in inv1}.isdisjoint({i["id"] for i in inv2})

    a1 = staging.artifact_rows(app1.project_id)
    a2 = staging.artifact_rows(app2.project_id)
    assert a1 and a2
    assert all(a["project_id"] == app1.project_id for a in a1)
    assert all(a["project_id"] == app2.project_id for a in a2)
    assert {a["id"] for a in a1}.isdisjoint({a["id"] for a in a2})

    # Cross-tenant read: carol is not in alice's org -> 404, no existence leak.
    assert (
        carol.get(f"/api/v1/projects/{app1.project_id}/first-responder/invocations").status_code
        == 404
    )
    assert (
        carol.get(f"/api/v1/projects/{app1.project_id}/first-responder/decisions").status_code
        == 404
    )
    report.check("cross-tenant read", 404, 404)


# ---------------------------------------------------------------------------
# Scenario H — adversarial model outputs cannot change authorization or
# evidence-confirmation semantics.
# ---------------------------------------------------------------------------


def test_h_agent_output_manipulation(staging, report):
    alice, bob = staging.login("alice"), staging.login("bob")
    app = staging.create_project(alice, bob)
    repo, sha = staging.checkout_owned_repo("repo-h")
    staging.bind_repo(app, repo)
    staging.index_snapshot(app.repo_id, sha)
    staging.register_app(app)
    staging.issue_token(app)
    staging.attest_mapping(app, commit_sha=sha)
    staging.set_mode(alice, app.project_id, "monitor")

    scripts = all_role_scripts(repo / "target")
    scripts[RuntimeAgentName.SCOUT] = adversarial_scout_script()
    fake = fake_provider(repo / "target", scripts=scripts)
    staging.use_gateway(gateway_factory(fake))

    assert staging.ingest(alice, app).status_code == 202
    staging.drain()

    inv = staging.by_agent(staging.invocations(alice, app.project_id))
    scout = inv["scout"]
    assert scout["status"] == INV.executed.value
    ex = scout["execution"]
    assert ex["typed_output"] is True
    # None of the injected claims changed semantics.
    assert ex["evidence_verified"] is False
    assert ex["confirmation"] == ConfirmationState.unverified.value
    assert ex["independent_verification_id"] is None
    report.check("adversarial output did not confirm evidence", "unverified", ex["confirmation"])

    decisions = staging.decisions(alice, app.project_id)
    assert decisions[0]["executed"] is False
    assert decisions[0]["confirmation"] == ConfirmationState.unverified.value
    assert decisions[0]["llm_prose_is_not_confirmation"] is True

    # The transcript records the denied tool calls and the schema rejection —
    # the runtime treated model output as untrusted.
    _, transcript = staging.artifact_json(ex["transcript_artifact_id"])
    raw = json.dumps(transcript)
    assert "http__request" in raw  # denied tool call recorded
    assert "SCHEMA_INVALID" in raw  # forged submit rejected by the strict schema
    report.check(
        "denied tool recorded", "http__request in transcript", True, ok="http__request" in raw
    )
    report.check(
        "schema rejection recorded",
        "SCHEMA_INVALID in transcript",
        True,
        ok="SCHEMA_INVALID" in raw,
    )

    # The persisted hypotheses carry no injected authority fields.
    _, output = staging.artifact_json(ex["output_artifact_id"])
    raw_out = json.dumps(output)
    for forged in ("verification_status", "grant_permissions", "decision_override"):
        assert forged not in raw_out
    # Authorization unchanged: still monitor, no execution/control jobs.
    mode = alice.get(f"/api/v1/projects/{app.project_id}/first-responder/mode").json()
    assert mode["intent"] == "monitor"
    assert not any(j["kind"].startswith("live_defense_execute") for j in staging.job_rows())


# ---------------------------------------------------------------------------
# Opt-in live-provider check. NOT part of the deterministic suite; requires
# RUN_LIVE_LLM_EVAL=1 and a real key (HACKATL_LIVE_ANTHROPIC_API_KEY), and it
# costs money. Never run in default CI.
# ---------------------------------------------------------------------------


@pytest.mark.live_llm
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_LLM_EVAL") != "1",
    reason="live provider eval is opt-in: set RUN_LIVE_LLM_EVAL=1 and provide a key",
)
def test_live_provider_scout_executes(staging, settings_override, report):
    key = os.environ.get("HACKATL_LIVE_ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("no HACKATL_LIVE_ANTHROPIC_API_KEY provided")
    settings_override(anthropic_api_key=key)
    staging.monkeypatch.setattr(llm, "TRANSPORT_OVERRIDE", None)

    alice, bob = staging.login("alice"), staging.login("bob")
    app = staging.create_project(alice, bob)
    repo, sha = staging.checkout_owned_repo("repo-live")
    staging.bind_repo(app, repo)
    staging.index_snapshot(app.repo_id, sha)
    staging.register_app(app)
    staging.issue_token(app)
    staging.attest_mapping(app, commit_sha=sha)
    staging.set_mode(alice, app.project_id, "monitor")

    assert staging.ingest(alice, app).status_code == 202
    staging.drain()
    scout = staging.by_agent(staging.invocations(alice, app.project_id))["scout"]
    assert scout["status"] == INV.executed.value
    assert scout["provider_mode"] == "live"
    report.check("live scout provider_mode", "live", scout["provider_mode"])
