"""Deterministic, schema-valid V0 example payloads (integration currency, docs/25).

These are CONTRACT EXAMPLES for consumer development and contract tests. They are
labeled fixtures — never present them as real assessment output.

    python -m shared.examples          # (re)write shared/fixtures/v0/*.json
    python -m shared.examples --check  # CI: fail if committed fixtures are stale
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from shared import (
    api,
    assessment,
    audit,
    events,
    evidence,
    findings,
    intelligence,
    live_defense,
    monitoring,
    review,
    rl,
    scope,
    tenancy,
)
from shared.audit import GENESIS_HASH, audit_hash

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "v0"
T0 = datetime(2026, 10, 17, 1, 0, 0, tzinfo=UTC)
HEAD = "b" * 40
BASE = "a" * 40
SHA = "c" * 64

ORG = "org_01JFIXTURE0000000000000ORG"
USR = "usr_01JFIXTURE0000000000000USR"
USR2 = "usr_01JFIXTURE000000000000USR2"
PRJ = "prj_01JFIXTURE0000000000000PRJ"
REP = "rep_01JFIXTURE0000000000000REP"
SNP = "snp_01JFIXTURE0000000000000SNP"
SCP = "scp_01JFIXTURE0000000000000SCP"
ASM = "asm_01JFIXTURE0000000000000ASM"
FND = "fnd_01JFIXTURE0000000000000FND"
EXP = "exp_01JFIXTURE0000000000000EXP"
ART = "art_01JFIXTURE0000000000000ART"
RUN = "run_01JFIXTURE0000000000000RUN"
PAT = "pat_01JFIXTURE0000000000000PAT"
APP = "app_01JFIXTURE0000000000000APP"
ITK = "itk_01JFIXTURE0000000000000ITK"
ARV = "arv_01JFIXTURE0000000000000ARV"
LPD = "lpd_01JFIXTURE0000000000000LPD"
LCT = "lct_01JFIXTURE0000000000000LCT"
CGR = "cgr_01JFIXTURE0000000000000CGR"
CCH = "cch_01JFIXTURE0000000000000CCH"
EST = "est_01JFIXTURE0000000000000EST"
REC = "rec_0123456789abcdef0123456789abcdef"
BIND = "a" * 64


def _span_ref(path: str, start: int, end: int, provenance: str) -> evidence.EvidenceRef:
    return evidence.EvidenceRef(
        kind=evidence.EvidenceKind.source_span,
        path=path,
        commit_sha=HEAD,
        span=evidence.SourceSpan(start_line=start, end_line=end),
        provenance=provenance,
    )


def _artifact_ref(kind: evidence.EvidenceKind, note: str) -> evidence.EvidenceRef:
    return evidence.EvidenceRef(
        kind=kind, artifact_id=ART, sha256=SHA, provenance="agent:verify", note=note
    )


def build() -> dict[str, BaseModel]:
    snap_ref = intelligence.SnapshotRef(
        project_id=PRJ, repo_id=REP, commit_sha=HEAD, snapshot_id=SNP, index_version="intel-0.1"
    )
    owner_rule = _span_ref("app/invoices.py", 40, 52, "code_intelligence.expectations@0.1")
    expectation = intelligence.BehavioralExpectation(
        id=EXP,
        snapshot_id=SNP,
        subject_ref="app.invoices.get_invoice",
        statement="A customer can only read invoices belonging to their own tenant.",
        kind=intelligence.ExpectationKind.ownership,
        sources=[_span_ref("tests/test_invoices.py", 10, 24, "code_intelligence.expectations@0.1")],
        confidence=0.9,
        origin=intelligence.ExpectationOrigin.extracted,
        status=intelligence.ExpectationStatus.confirmed,
        data_sensitivity=intelligence.DataSensitivity.financial,
    )
    pack = intelligence.ContextPack(
        id="ctx_01JFIXTURE0000000000000CTX",
        snapshot_ref=snap_ref,
        request=intelligence.ContextPackRequest(
            snapshot_ref=snap_ref,
            purpose=intelligence.ContextPurpose.scout,
            focus=["app.invoices.get_invoice"],
            token_budget=8000,
        ),
        chunks=[
            intelligence.ContextChunk(
                provenance=owner_rule,
                content="def get_invoice(invoice_id, user):\n    return db.invoices.get(invoice_id)\n",
                token_estimate=24,
            )
        ],
        token_budget=8000,
        token_count=24,
        provenance=[owner_rule],
        created_at=T0,
    )
    finding = findings.Finding(
        id=FND,
        assessment_id=ASM,
        snapshot_id=SNP,
        commit_sha=HEAD,
        kind=findings.FindingKind.security,
        title="Invoice lookup no longer enforces tenant ownership (IDOR)",
        status=findings.FindingStatus.validated,
        severity=findings.SeverityAssessment(
            level=findings.SeverityLevel.high,
            factors=findings.SeverityFactors(
                reachability="authenticated HTTP route",
                privileges_required="any customer",
                data_sensitivity="financial",
                verified_path=True,
            ),
            rationale="Probe reproduced cross-tenant read in sandbox.",
        ),
        subject_refs=["app.invoices.get_invoice"],
        expectation_ids=[EXP],
        evidence=[
            owner_rule,
            _artifact_ref(evidence.EvidenceKind.sandbox_run, "probe check output"),
        ],
        confidence=0.95,
        produced_by_run_id=RUN,
        history=[
            findings.StatusChange(
                from_status=findings.FindingStatus.hypothesis,
                to_status=findings.FindingStatus.validated,
                at=T0,
                actor="agent:probe",
                reason="ownership check confirmed",
            )
        ],
        created_at=T0,
        updated_at=T0,
    )
    patch = findings.PatchCandidate(
        id=PAT,
        finding_id=FND,
        attempt=1,
        diff_artifact_id=ART,
        diff_sha256=SHA,
        base_commit_sha=HEAD,
        worktree_ref=".worktrees/asm/pat-1",
        files_changed=["app/invoices.py"],
        tests_added=["tests/test_invoice_tenant_isolation.py"],
        produced_by_run_id=RUN,
        rationale="Re-add tenant filter to the invoice query.",
        created_at=T0,
    )
    verification = findings.VerificationResult(
        id="ver_01JFIXTURE0000000000000VER",
        patch_id=PAT,
        verdict=findings.VerificationVerdict.accepted,
        checks=[
            findings.VerificationCheck(
                name=n,
                passed=True,
                evidence=[_artifact_ref(evidence.EvidenceKind.test_run, n.value)],
            )
            for n in findings.VerificationCheckName
        ],
        sandbox_run_ids=["sbx-fixture-1"],
        reasons=[],
        produced_by_run_id=RUN,
        created_at=T0,
    )
    run = assessment.AgentRun(
        id=RUN,
        assessment_id=ASM,
        agent=assessment.AgentName.probe,
        step_key="validation",
        attempt=1,
        status=assessment.AgentRunStatus.succeeded,
        provider_mode="fake",
        model_id="claude-opus-5-5",
        prompt_version="probe@0.1",
        tool_calls=[
            assessment.ToolCallRecord(
                turn=1,
                tool_name="run_check",
                input_sha256=SHA,
                outcome=assessment.ToolCallOutcome.ok,
                duration_ms=812,
                output_artifact_id=ART,
            )
        ],
        usage=tenancy.Usage(
            input_tokens=5200, output_tokens=640, usd=0.0336, llm_calls=2, tool_calls=1
        ),
        started_at=T0,
        ended_at=T0,
    )
    asm = assessment.Assessment(
        id=ASM,
        project_id=PRJ,
        snapshot_id=SNP,
        commit_sha=HEAD,
        repo_id=REP,
        scope_id=SCP,
        trigger=assessment.AssessmentTrigger.monitoring,
        state=assessment.AssessmentState.VALIDATION,
        budget=tenancy.Budget(),
        created_at=T0,
        updated_at=T0,
    )
    impact = intelligence.ImpactSet(
        repo_id=REP,
        base_sha=BASE,
        head_sha=HEAD,
        resolution=intelligence.ImpactResolution.path_only,
        changed_paths=["app/invoices.py"],
    )
    event = monitoring.MonitoringEvent(
        id="evt_01JFIXTURE0000000000000EVT",
        project_id=PRJ,
        repo_id=REP,
        source=monitoring.EventSource.github,
        type=monitoring.EventType.push,
        occurred_at=T0,
        received_at=T0,
        dedupe_key="github:delivery:72d3162e-cc78-11e3-81ab-4c9367dc0958",
        payload_artifact_id=ART,
        commit_range=monitoring.CommitRange(base_sha=BASE, head_sha=HEAD),
        ref="refs/heads/main",
        simulated=True,
        status=monitoring.EventStatus.processed,
        impact=impact,
    )
    rrq = monitoring.ReassessmentRequest(
        id="rrq_01JFIXTURE0000000000000RRQ",
        project_id=PRJ,
        repo_id=REP,
        event_ids=[event.id],
        scope=monitoring.ReassessmentScope.targeted,
        head_sha=HEAD,
        targets=["app/invoices.py"],
        status=monitoring.ReassessmentStatus.started,
        reason="non-test code changed under active scope",
        assessment_id=ASM,
        created_at=T0,
    )
    nodes = [
        rl.NodeSignals(node=n, criticality=c, exposed=n in ("gateway", "api"))
        for n, c in (("gateway", 0.3), ("api", 0.5), ("auth", 0.7), ("payments", 0.9), ("db", 1.0))
    ]
    rec = rl.DefenseRecommendation(
        id="rec_0123456789abcdef0123456789abcdef",
        project_id=PRJ,
        policy_version="DefenseSimEnv-v0@cccccccccccc",
        checkpoint_sha256=SHA,
        action="raise_monitoring",
        node="payments",
        q_margin=0.42,
        top_actions=[
            rl.ActionScore(action="raise_monitoring", node="payments", q_value=1.3),
            rl.ActionScore(action="noop", node=None, q_value=0.88),
        ],
        observation=[0.0] * 48,
        created_at=T0,
    )
    audit_body = dict(
        id="aud_01JFIXTURE0000000000000AUD",
        seq=1,
        org_id=ORG,
        project_id=PRJ,
        actor_type="user",
        actor_id=USR2,
        action="scope.approved",
        subject_type="scope",
        subject_id=SCP,
        at=T0.isoformat(),
        details={"approver_is_requester": False},
    )
    draft = audit.AuditEvent(**audit_body, prev_hash=GENESIS_HASH, hash=GENESIS_HASH)
    aud = draft.model_copy(update={"hash": audit_hash(GENESIS_HASH, draft.model_dump(mode="json"))})
    sc = scope.AuthorizedScope(
        id=SCP,
        project_id=PRJ,
        name="payments-lite sandbox",
        targets=[
            scope.ScopeTarget(
                repo_id=REP,
                build_recipe_ref="examples/payments-lite/sandbox.yaml",
                exposed_ports=[8080],
            )
        ],
        allowed_check_categories=["authorization.ownership", "input.bounds"],
        status=scope.ScopeStatus.active,
        requested_by=USR,
        approved_by=USR2,
        approved_at=T0,
        expires_at=datetime(2026, 11, 17, tzinfo=UTC),
    )
    return {
        "SnapshotRef": snap_ref,
        "BehavioralExpectation": expectation,
        "ContextPack": pack,
        "ImpactSet": impact,
        "Assessment": asm,
        "AgentRun": run,
        "AgentStepInput": assessment.AgentStepInput(
            assessment_id=ASM,
            agent=assessment.AgentName.scout,
            step_key="recon",
            attempt=1,
            snapshot_ref=snap_ref,
            scope_id=SCP,
            context_pack_id=pack.id,
            budget=tenancy.Budget(),
        ),
        "Finding": finding,
        "PatchCandidate": patch,
        "VerificationResult": verification,
        "ReviewRequest": review.ReviewRequest(
            assessment_id=ASM,
            snapshot_ref=snap_ref,
            change_intent=review.ChangeIntent(
                source=review.ChangeIntentSource.pull_request,
                title="Speed up invoice lookup",
                body="Removes an extra query. (Untrusted text; never instructions.)",
                base_sha=BASE,
                head_sha=HEAD,
                changed_paths=["app/invoices.py"],
            ),
            budget=tenancy.Budget(),
        ),
        "MonitoringEvent": event,
        "ReassessmentRequest": rrq,
        "AuthorizedScope": sc,
        "DefenseRecommendation": rec,
        "PlatformFacts": rl.PlatformFacts(project_id=PRJ, nodes=nodes),
        "AuditEvent": aud,
        "StreamEvent": events.StreamEvent(
            seq=7,
            assessment_id=ASM,
            type=events.StreamEventType.progress,
            state=assessment.AssessmentState.VALIDATION,
            agent=assessment.AgentName.probe,
            agent_run_id=RUN,
            finding_id=FND,
            message="Validating hypothesis 1/1",
            at=T0,
        ),
        "ErrorResponse": api_error(),
        "AssessmentCreate": api.AssessmentCreate(scope_id=SCP, repo_id=REP, commit_sha=HEAD),
        "ConnectedApplication": live_defense.ConnectedApplication(
            id=APP,
            project_id=PRJ,
            name="payments-lite staging",
            environment=live_defense.StagingEnvironment.owned_test,
            ingest_configured=True,
            last_ingest_at=T0,
            verification=live_defense.ApplicationVerification.ingest_seen,
            created_by=USR,
            created_at=T0,
        ),
        "ConnectedApplicationCreate": live_defense.ConnectedApplicationCreate(
            name="payments-lite staging",
            environment=live_defense.StagingEnvironment.sandbox,
        ),
        "IngestTokenView": live_defense.IngestTokenView(
            id=ITK,
            project_id=PRJ,
            application_id=APP,
            created_at=T0,
            revoked_at=None,
            last_used_at=T0,
        ),
        "DefenseHealth": live_defense.DefenseHealth(project_id=PRJ, queue_depth=0),
        "IngestTokenRotated": live_defense.IngestTokenRotated(
            id=ITK,
            project_id=PRJ,
            application_id=APP,
            token="hkt_ing_fixture_shown_once",
            created_at=T0,
            revoked_ids=[],
        ),
        "PilotTrailEntry": live_defense.PilotTrailEntry(
            at=T0,
            action="ingest_token.created",
            subject_type="ingest_token",
            subject_id=ITK,
            detail="shown_once",
        ),
        "PilotReport": live_defense.PilotReport(
            project_id=PRJ,
            generated_at=T0,
            ingest_windows=0,
            shadow_decisions=0,
            reviews=0,
            incidents=0,
            health=live_defense.DefenseHealth(project_id=PRJ, queue_depth=0),
        ),
        "ComponentNode": live_defense.ComponentNode(
            id=APP, label="payments-lite staging", kind=live_defense.ComponentNodeKind.application
        ),
        "ComponentLink": live_defense.ComponentLink(source_id=APP, target_id="GET /health"),
        "ComponentObservation": live_defense.ComponentObservation(
            node_id="GET /health",
            state=live_defense.ComponentHealthState.unknown,
            last_checked_at=T0,
            source=live_defense.ComponentObservationSource.ingest,
            simulated=True,
            note="Latest window was scored; not a health check.",
        ),
        "ComponentGraph": live_defense.ComponentGraph(project_id=PRJ, generated_at=T0),
        "AnalystReview": live_defense.AnalystReview(
            id=ARV,
            project_id=PRJ,
            recommendation_id=REC,
            decision=live_defense.AnalystReviewDecision.needs_investigation,
            reason="Need the linked runtime event before accepting.",
            reviewed_by=USR,
            reviewed_at=T0,
        ),
        "AnalystReviewCreate": live_defense.AnalystReviewCreate(
            decision=live_defense.AnalystReviewDecision.accept,
            reason="Recorded for the shadow pilot; does not execute.",
        ),
        "LivePolicyDecision": live_defense.LivePolicyDecision(
            id=LPD,
            project_id=PRJ,
            application_id=APP,
            created_at=T0,
            window_end=T0,
            telemetry_source="owned_staging",
            simulated=False,
            producer=live_defense.ShadowProducer.rules,
            rules_ran=True,
            inference_ran=False,
            inference_status=live_defense.InferenceStatus.skipped_quiet_window,
            action="noop",
            node=None,
            top_actions=None,
            q_margin=None,
            observation=None,
            policy_version=None,
            checkpoint_sha256=None,
            abstention_reason="Quiet window: frozen v6 is not a trustworthy live decision.",
            observation_complete=True,
            feature_schema_ok=True,
            action_mask_valid=True,
            freshness_ok=True,
            authorization_context=live_defense.AuthorizationContext.missing,
            evidence_event_ids=[],
            rule_hits=[],
            principal_targets=[],
            feature_mapping_note=None,
        ),
        "AuthorizationCheckResult": live_defense.AuthorizationCheckResult(
            name="authenticated_session",
            passed=True,
            reason="Actor is the authenticated session.",
        ),
        "ControlTarget": live_defense.ControlTarget(
            type=live_defense.LiveControlTargetType.route,
            value="GET /payments/{payment_id}",
        ),
        "ControlGrant": live_defense.ControlGrant(
            id=CGR,
            project_id=PRJ,
            application_id=APP,
            allowed_kinds=[
                live_defense.LiveControlKind.rate_limit,
                live_defense.LiveControlKind.block_source,
                live_defense.LiveControlKind.increase_logging,
                live_defense.LiveControlKind.escalate,
            ],
            max_duration_s=300,
            hourly_budget=5,
            created_by=USR,
            created_at=T0,
        ),
        "ControlGrantCreate": live_defense.ControlGrantCreate(
            application_id=APP,
            allowed_kinds=[live_defense.LiveControlKind.rate_limit],
            max_duration_s=300,
            hourly_budget=5,
        ),
        "ControlChannelView": live_defense.ControlChannelView(
            id=CCH,
            project_id=PRJ,
            application_id=APP,
            host="127.0.0.1",
            port=18080,
            created_at=T0,
        ),
        "ControlChannelCreate": live_defense.ControlChannelCreate(port=18080),
        "ControlChannelCreated": live_defense.ControlChannelCreated(
            id=CCH,
            project_id=PRJ,
            application_id=APP,
            host="127.0.0.1",
            port=18080,
            created_at=T0,
            hmac_secret="hkt_ctl_exampleonly_notsecret",
        ),
        "ControlAuthorizationCreate": live_defense.ControlAuthorizationCreate(
            kind=live_defense.LiveControlKind.rate_limit,
            target=live_defense.ControlTarget(
                type=live_defense.LiveControlTargetType.route,
                value="GET /payments/{payment_id}",
            ),
            duration_s=60,
            rationale="Owned-test rate limit after a staged finding.",
            live_policy_decision_id=LPD,
            max_requests=2,
        ),
        "LiveControlVerification": live_defense.LiveControlVerification(
            observed_effect=True,
            adapter_http_status=200,
            probe_http_statuses=[200, 429],
            method="real_http_probes",
            detail="Second fixture request was 429 after a 1-request rate limit.",
            verified_at=T0,
        ),
        "LiveControl": live_defense.LiveControl(
            id=LCT,
            project_id=PRJ,
            application_id=APP,
            live_policy_decision_id=LPD,
            grant_id=CGR,
            kind=live_defense.LiveControlKind.rate_limit,
            target=live_defense.ControlTarget(
                type=live_defense.LiveControlTargetType.route,
                value="GET /payments/{payment_id}",
            ),
            duration_s=60,
            status=live_defense.LiveControlStatus.verified,
            origin=live_defense.LiveControlOrigin.analyst,
            binding_sha256=BIND,
            requested_by=USR,
            requested_at=T0,
            authorized_at=T0,
            executing_at=T0,
            verified_at=T0,
            expires_at=T0,
            checks=[
                live_defense.AuthorizationCheckResult(
                    name="authenticated_session",
                    passed=True,
                    reason="Actor is the authenticated session.",
                )
            ],
            max_requests=2,
            rationale="Owned-test rate limit after a staged finding.",
        ),
        "EmergencyStop": live_defense.EmergencyStop(
            id=EST,
            project_id=PRJ,
            application_id=APP,
            active=True,
            requested_by=USR,
            requested_at=T0,
            verified_cleared=False,
            note="Kill switch for the owned-test app.",
        ),
        "EmergencyStopCreate": live_defense.EmergencyStopCreate(
            application_id=APP,
            note="Kill switch for the owned-test app.",
        ),
        "LiveControlRollbackCreate": live_defense.LiveControlRollbackCreate(
            reason="Analyst requested rollback after verification.",
        ),
    }


def api_error() -> BaseModel:
    from shared.errors import ErrorBody, ErrorCode, ErrorResponse

    return ErrorResponse(
        error=ErrorBody(
            code=ErrorCode.SCOPE_DENIED,
            message="Scope scp_… is not active",
            request_id="req_01JFIXTURE0000000000000REQ",
        )
    )


def render() -> dict[Path, str]:
    return {
        FIXTURE_DIR / f"{name}.json": json.dumps(
            model.model_dump(mode="json"), indent=2, sort_keys=True
        )
        + "\n"
        for name, model in build().items()
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    args = p.parse_args(argv)
    stale = [
        path for path, text in render().items() if not path.exists() or path.read_text() != text
    ]
    if args.check:
        if stale:
            print("stale fixtures:", *map(str, stale), sep="\n  ", file=sys.stderr)
            return 1
        return 0
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for path, text in render().items():
        path.write_text(text)
    print(f"wrote {len(render())} fixtures ({len(stale)} changed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
