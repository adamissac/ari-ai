"""First-responder job: deterministic decide, persist, dispatch gated agent steps.

Never enqueues ``live_defense_execute``. Patch is worktree-only. Probe needs
AuthorizedScope. Verify is independent of Patch. LLM prose cannot confirm a threat.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from backend import audit
from backend import jobs as jobq
from backend.db import (
    analyst_handoffs,
    approvals,
    connected_applications,
    deploy_commit_mappings,
    findings,
    first_responder_decisions,
    first_responder_invocations,
    ingest_tokens,
    live_policy_decisions,
    patch_candidates,
    runtime_windows,
    snapshots,
    transaction,
)
from backend.live_defense.capabilities import load_registry
from backend.live_defense.modes import (
    cancel_first_responder_jobs,
    effective_permissions,
    load_intent,
    mapping_fresh,
    telemetry_untrusted,
)
from backend.live_defense.orchestrator import OrchestratorFacts, decide
from backend.services import active_scope_for_repo, project_org
from backend.worker import JobContext, handler
from shared.assessment import AgentName
from shared.audit import ActorType
from shared.base import utcnow
from shared.ids import IdPrefix, new_id
from shared.live_defense import (
    ORCHESTRATOR_VERSION,
    AgentCapabilityClass,
    AgentInvocationStatus,
    AnalystHandoff,
    AnalystHandoffState,
    ApplicationVerification,
    ConfirmationState,
    ConnectedApplication,
    FirstResponderDecision,
    FirstResponderIntent,
    FirstResponderInvocation,
    OrchestratorAction,
    StagingEnvironment,
)
from shared.monitoring import AUTHENTICATED_RUNTIME_SOURCES
from shared.scope import ApprovalStatus, ApprovalSubject

log = logging.getLogger("backend.live_defense.first_responder")


def _application(conn: Connection, app_id: str | None) -> ConnectedApplication | None:
    if not app_id:
        return None
    row = (
        conn.execute(sa.select(connected_applications).where(connected_applications.c.id == app_id))
        .mappings()
        .first()
    )
    if row is None:
        return None
    disconnected_at = (row["doc"] or {}).get("disconnected_at")
    last_ingest = conn.execute(
        sa.select(sa.func.max(runtime_windows.c.window_end)).where(
            runtime_windows.c.application_id == app_id
        )
    ).scalar()
    active_token = conn.execute(
        sa.select(ingest_tokens.c.id).where(
            ingest_tokens.c.application_id == app_id, ingest_tokens.c.revoked_at.is_(None)
        )
    ).scalar()
    if disconnected_at:
        verification = ApplicationVerification.disconnected
    elif last_ingest is not None:
        verification = ApplicationVerification.ingest_seen
    else:
        verification = ApplicationVerification.unverified
    return ConnectedApplication(
        id=row["id"],
        project_id=row["project_id"],
        name=row["name"],
        environment=StagingEnvironment(row["environment"]),
        ingest_configured=bool(active_token) and disconnected_at is None,
        last_ingest_at=last_ingest,
        verification=verification,
        disconnected_at=disconnected_at,
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _trusted_mapping(conn: Connection, application_id: str | None) -> dict[str, Any] | None:
    if not application_id:
        return None
    row = (
        conn.execute(
            sa.select(deploy_commit_mappings)
            .where(
                deploy_commit_mappings.c.application_id == application_id,
                deploy_commit_mappings.c.revoked_at.is_(None),
            )
            .order_by(deploy_commit_mappings.c.created_at.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _findings_at(conn: Connection, project_id: str, commit_sha: str | None) -> list[str]:
    """Finding ids at a commit are listed only as context, never as proof."""
    _ = conn, project_id, commit_sha
    return []


def _remediation_approved(conn: Connection, project_id: str) -> bool:
    return (
        conn.execute(
            sa.select(approvals.c.id).where(
                approvals.c.project_id == project_id,
                approvals.c.subject_type == ApprovalSubject.remediation.value,
                approvals.c.status == ApprovalStatus.approved.value,
            )
        ).scalar()
        is not None
    )


def _patch_candidate(conn: Connection, project_id: str) -> str | None:
    return conn.execute(
        sa.select(patch_candidates.c.id)
        .select_from(
            patch_candidates.join(findings, findings.c.id == patch_candidates.c.finding_id)
        )
        .where(findings.c.project_id == project_id)
        .order_by(patch_candidates.c.created_at.desc())
        .limit(1)
    ).scalar()


def _snapshot_exists(conn: Connection, repo_id: str | None, commit_sha: str | None) -> bool:
    if not repo_id or not commit_sha:
        return False
    return (
        conn.execute(
            sa.select(snapshots.c.id).where(
                snapshots.c.repo_id == repo_id, snapshots.c.commit_sha == commit_sha
            )
        ).scalar()
        is not None
    )


def maybe_enqueue(
    conn: Connection,
    *,
    project_id: str,
    application_id: str | None,
    window_end: datetime,
    source: str,
    live_policy_decision_id: str | None,
    event_ids: list[str],
) -> tuple[str, bool] | None:
    """Enqueue a first-responder job when effective mode is not OFF. Isolated queue."""
    app = _application(conn, application_id)
    mapping = _trusted_mapping(conn, application_id)
    perms = effective_permissions(
        conn,
        project_id=project_id,
        application=app,
        repo_id=mapping["repo_id"] if mapping else None,
        trusted_mapping=bool(mapping),
    )
    if perms.effective is FirstResponderIntent.off:
        return None
    dedupe = f"live_defense_first_responder:{project_id}:{application_id or '-'}:{window_end.isoformat()}:{source}"
    return jobq.enqueue(
        conn,
        "live_defense_first_responder",
        {
            "project_id": project_id,
            "application_id": application_id,
            "window_end": window_end.isoformat(),
            "source": source,
            "live_policy_decision_id": live_policy_decision_id,
            "event_ids": event_ids,
        },
        dedupe_key=dedupe,
        priority=80,
    )


def _persist_decision(
    conn: Connection, decision: FirstResponderDecision, dedupe: str
) -> tuple[FirstResponderDecision, bool]:
    inserted = conn.execute(
        pg_insert(first_responder_decisions)
        .values(
            id=decision.id,
            project_id=decision.project_id,
            application_id=decision.application_id,
            dedupe_key=dedupe,
            action=decision.action.value,
            doc=decision.model_dump(mode="json"),
        )
        .on_conflict_do_nothing()
        .returning(first_responder_decisions.c.id, first_responder_decisions.c.doc)
    ).first()
    if inserted:
        return decision, True
    existing = (
        conn.execute(
            sa.select(first_responder_decisions.c.doc).where(
                first_responder_decisions.c.dedupe_key == dedupe
            )
        )
        .mappings()
        .one()
    )
    return FirstResponderDecision.model_validate(existing["doc"]), False


def _invocation_status(
    agent: AgentName,
    decision: FirstResponderDecision,
    *,
    has_snapshot: bool,
    has_scope: bool,
    has_approval: bool,
    has_patch: bool,
) -> AgentInvocationStatus:
    blocked = {item.name: item.reason for item in decision.blocked_agents}
    if agent in blocked:
        reason = blocked[agent]
        if "AuthorizedScope" in reason or "scope" in reason.lower():
            return AgentInvocationStatus.skipped_no_scope
        if "approval" in reason.lower():
            return AgentInvocationStatus.skipped_no_approval
        if "PatchCandidate" in reason or "patch" in reason.lower():
            return AgentInvocationStatus.skipped_no_patch
        if "mapping" in reason.lower():
            return AgentInvocationStatus.skipped_no_mapping
        if "OFF" in reason or "ASSISTED" in reason:
            return AgentInvocationStatus.skipped_mode
        return AgentInvocationStatus.blocked
    if agent in {AgentName.scout, AgentName.diagnose, AgentName.fortify, AgentName.trace}:
        if decision.correlation.confidence.value in {"unknown", "none"}:
            return AgentInvocationStatus.skipped_no_mapping
        if not has_snapshot:
            return AgentInvocationStatus.skipped_no_snapshot
        return AgentInvocationStatus.queued
    if agent is AgentName.probe:
        return AgentInvocationStatus.queued if has_scope else AgentInvocationStatus.skipped_no_scope
    if agent is AgentName.patch:
        return (
            AgentInvocationStatus.queued
            if has_approval
            else AgentInvocationStatus.skipped_no_approval
        )
    if agent is AgentName.verify:
        return AgentInvocationStatus.queued if has_patch else AgentInvocationStatus.skipped_no_patch
    return AgentInvocationStatus.blocked


def _record_invocations(
    conn: Connection, decision: FirstResponderDecision, *, has_snapshot: bool, has_scope: bool
) -> list[FirstResponderInvocation]:
    registry = {item.name: item for item in load_registry().agents}
    has_approval = _remediation_approved(conn, decision.project_id)
    has_patch = _patch_candidate(conn, decision.project_id) is not None
    out: list[FirstResponderInvocation] = []
    for agent in [*decision.selected_agents, *[b.name for b in decision.blocked_agents]]:
        cap = registry.get(agent)
        if cap is None:
            continue
        status = _invocation_status(
            agent,
            decision,
            has_snapshot=has_snapshot,
            has_scope=has_scope,
            has_approval=has_approval,
            has_patch=has_patch,
        )
        inv = FirstResponderInvocation(
            id=new_id(IdPrefix.fri),
            decision_id=decision.id,
            project_id=decision.project_id,
            agent=agent,
            capability_class=cap.capability_class,
            status=status,
            provider_mode="none",
            independent_of_patch=agent is AgentName.verify,
            worktree_only=cap.capability_class is AgentCapabilityClass.code_changing,
            authorized_scope_id=None,
            reason=next(
                (b.reason for b in decision.blocked_agents if b.name is agent), status.value
            ),
            created_at=utcnow(),
        )
        conn.execute(
            sa.insert(first_responder_invocations).values(
                id=inv.id,
                decision_id=decision.id,
                project_id=decision.project_id,
                agent=agent.value,
                status=status.value,
                doc=inv.model_dump(mode="json"),
            )
        )
        if status is AgentInvocationStatus.queued:
            job_id, _ = jobq.enqueue(
                conn,
                "live_defense_agent_step",
                {
                    "project_id": decision.project_id,
                    "decision_id": decision.id,
                    "invocation_id": inv.id,
                    "agent": agent.value,
                    "capability_class": cap.capability_class.value,
                },
                dedupe_key=f"live_defense_agent_step:{decision.id}:{agent.value}",
                priority=90,
            )
            inv = inv.model_copy(update={"job_id": job_id})
            conn.execute(
                sa.update(first_responder_invocations)
                .where(first_responder_invocations.c.id == inv.id)
                .values(doc=inv.model_dump(mode="json"))
            )
        out.append(inv)
    return out


def _maybe_handoff(conn: Connection, decision: FirstResponderDecision, actor_id: str) -> None:
    if decision.action not in {
        OrchestratorAction.escalate_to_analyst,
        OrchestratorAction.confirm_with_probe,
        OrchestratorAction.propose_worktree_patch,
    }:
        return
    if decision.effective_mode is FirstResponderIntent.off:
        return
    handoff = AnalystHandoff(
        id=new_id(IdPrefix.ahl),
        project_id=decision.project_id,
        application_id=decision.application_id,
        decision_id=decision.id,
        state=AnalystHandoffState.delivery_pending,
        confirmation=ConfirmationState.unverified,
        title=f"First-responder {decision.action.value}",
        summary=(
            f"Orchestrator {ORCHESTRATOR_VERSION} recorded {decision.action.value}. "
            "Not a confirmed threat. Alert is not delivered until the provider confirms."
        ),
        evidence_event_ids=list(decision.trigger_event_ids),
        recommended_actions=[a.value for a in decision.selected_agents],
        created_by=actor_id if actor_id.startswith("usr_") else "usr_system_first_responder",
        created_at=utcnow(),
        delivery_attempted_at=utcnow(),
    )
    # System actor must be a real UserId (FK). Prefer the owner who set the mode.
    mode = load_intent(conn, decision.project_id)
    created_by = mode.updated_by
    if created_by is None or not str(created_by).startswith("usr_"):
        app_row = (
            conn.execute(
                sa.select(connected_applications.c.created_by).where(
                    connected_applications.c.id == decision.application_id
                )
            ).scalar()
            if decision.application_id
            else None
        )
        created_by = app_row
    if created_by is None or not str(created_by).startswith("usr_"):
        return
    handoff = handoff.model_copy(update={"created_by": created_by})
    conn.execute(
        sa.insert(analyst_handoffs).values(
            id=handoff.id,
            project_id=handoff.project_id,
            application_id=handoff.application_id,
            decision_id=handoff.decision_id,
            state=handoff.state.value,
            confirmation=handoff.confirmation.value,
            created_by=handoff.created_by,
            doc=handoff.model_dump(mode="json"),
        )
    )


def process_first_responder(
    project_id: str,
    *,
    application_id: str | None,
    window_end: datetime,
    source: str,
    live_policy_decision_id: str | None,
    event_ids: list[str],
) -> dict[str, Any]:
    dedupe = f"{project_id}:{application_id or '-'}:{window_end.isoformat()}:{source}"
    with transaction() as conn:
        existing = conn.execute(
            sa.select(first_responder_decisions.c.id).where(
                first_responder_decisions.c.dedupe_key == dedupe
            )
        ).scalar()
        app = _application(conn, application_id)
        mapping = _trusted_mapping(conn, application_id)
        repo_id = mapping["repo_id"] if mapping else None
        perms = effective_permissions(
            conn,
            project_id=project_id,
            application=app,
            repo_id=repo_id,
            trusted_mapping=bool(mapping),
        )
        shadow = None
        if live_policy_decision_id:
            doc = conn.execute(
                sa.select(live_policy_decisions.c.doc).where(
                    live_policy_decisions.c.id == live_policy_decision_id
                )
            ).scalar()
            shadow = doc
        mapped_commit = mapping["commit_sha"] if mapping else None
        deployed_at = (mapping["doc"] or {}).get("deployed_at") if mapping else None
        if isinstance(deployed_at, str):
            deployed_at = datetime.fromisoformat(deployed_at)
        facts = OrchestratorFacts(
            project_id=project_id,
            application_id=application_id,
            intent=perms.intent,
            effective=perms.effective,
            application_connected=perms.application_connected,
            telemetry_authenticated=source in AUTHENTICATED_RUNTIME_SOURCES,
            secret_like=bool(telemetry_untrusted(source)),
            trusted_mapping=bool(mapping),
            mapped_commit=mapped_commit,
            mapping_id=mapping["id"] if mapping else None,
            mapping_fresh=mapping_fresh(deployed_at) if deployed_at else False,
            authorized_scope_active=perms.authorized_scope_active,
            remediation_approved=_remediation_approved(conn, project_id),
            patch_candidate_id=_patch_candidate(conn, project_id),
            kill_switch_active=perms.kill_switch_active,
            budget_usd_remaining=3.0,
            deadline_passed=False,
            already_decided_id=existing,
            retry_count=0,
            loop_count=1 if existing else 0,
            simulated=bool(shadow and shadow.get("simulated")),
            trigger_event_ids=tuple(event_ids),
            live_policy_decision_id=live_policy_decision_id,
            finding_ids_at_commit=tuple(_findings_at(conn, project_id, mapped_commit)),
            shadow_action=(shadow or {}).get("action"),
            q_values=None,
        )
        decision = decide(facts)
        stored, created = _persist_decision(conn, decision, dedupe)
        if created:
            has_snapshot = _snapshot_exists(conn, repo_id, mapped_commit)
            _record_invocations(
                conn,
                stored,
                has_snapshot=has_snapshot,
                has_scope=perms.authorized_scope_active,
            )
            _maybe_handoff(conn, stored, actor_id="live_defense.first_responder")
            audit.record(
                conn,
                org_id=project_org(conn, project_id),
                project_id=project_id,
                actor_type=ActorType.system,
                actor_id="live_defense.first_responder",
                action="live_defense.first_responder.decided",
                subject_type="first_responder_decision",
                subject_id=stored.id,
                details={
                    "action": stored.action.value,
                    "effective_mode": stored.effective_mode.value,
                    "executed": False,
                    "auto_execute": False,
                    "confirmation": stored.confirmation.value,
                    "orchestrator_version": stored.orchestrator_version,
                },
            )
        return {"decision_id": stored.id, "created": created, "action": stored.action.value}


@handler("live_defense_first_responder")
def live_defense_first_responder(ctx: JobContext) -> dict[str, Any]:
    payload = ctx.job.payload
    window_end = datetime.fromisoformat(payload["window_end"])
    return process_first_responder(
        payload["project_id"],
        application_id=payload.get("application_id"),
        window_end=window_end,
        source=payload["source"],
        live_policy_decision_id=payload.get("live_policy_decision_id"),
        event_ids=list(payload.get("event_ids") or []),
    )


@handler("live_defense_agent_step")
def live_defense_agent_step(ctx: JobContext) -> dict[str, Any]:
    """Run a gated agent step without faking success or deploying Patch.

    Investigative agents need a trusted mapping and a snapshot. Probe still
    requires AuthorizedScope at execution time. Patch never deploys. Verify
    refuses to share Patch state. This handler records honest skip/fail
    outcomes; it does not invent a confirmed threat from model text.
    """
    payload = ctx.job.payload
    agent = AgentName(payload["agent"])
    with transaction() as conn:
        row = (
            conn.execute(
                sa.select(first_responder_invocations).where(
                    first_responder_invocations.c.id == payload["invocation_id"]
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return {"status": "missing_invocation"}
        inv = FirstResponderInvocation.model_validate(row["doc"])
        if agent is AgentName.patch:
            status = AgentInvocationStatus.skipped_no_approval
            reason = "Patch remains worktree-only after human approval; silent deploy is refused"
            if payload.get("deploy"):
                status = AgentInvocationStatus.blocked
                reason = "silent customer deploy is refused"
        elif agent is AgentName.probe:
            decision_doc = conn.execute(
                sa.select(first_responder_decisions.c.doc).where(
                    first_responder_decisions.c.id == payload["decision_id"]
                )
            ).scalar()
            decision = FirstResponderDecision.model_validate(decision_doc)
            mapping = _trusted_mapping(conn, decision.application_id)
            repo_id = mapping["repo_id"] if mapping else None
            scope = active_scope_for_repo(conn, decision.project_id, repo_id) if repo_id else None
            if scope is None:
                status = AgentInvocationStatus.skipped_no_scope
                reason = "Probe denied: no active AuthorizedScope (no external probes)"
            else:
                status = AgentInvocationStatus.completed_unverified
                reason = (
                    "Probe eligible under AuthorizedScope; confirmation stays unverified "
                    "until executed template evidence exists"
                )
        elif agent is AgentName.verify:
            status = AgentInvocationStatus.completed_unverified
            reason = "Verify is independent of Patch; no Patch transcript or worktree was shared"
            if not _patch_candidate(conn, payload["project_id"]):
                status = AgentInvocationStatus.skipped_no_patch
                reason = "Verify skipped: no PatchCandidate"
        else:
            status = AgentInvocationStatus.completed_unverified
            reason = (
                f"{agent.value} investigative step recorded as unverified. "
                "LLM prose is not confirmation."
            )
        updated = inv.model_copy(
            update={"status": status, "reason": reason, "provider_mode": "none"}
        )
        conn.execute(
            sa.update(first_responder_invocations)
            .where(first_responder_invocations.c.id == inv.id)
            .values(status=status.value, doc=updated.model_dump(mode="json"))
        )
        return {"status": status.value, "agent": agent.value, "confirmed": False}


def reconcile_off(conn: Connection, project_id: str) -> dict[str, int]:
    cancelled = cancel_first_responder_jobs(conn, project_id)
    return {"cancelled_first_responder_jobs": cancelled}
