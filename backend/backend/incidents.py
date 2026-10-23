"""Human incident handling aligned to NIST SP 800-61r3. No infrastructure actions."""

from __future__ import annotations

from typing import NoReturn

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend import audit
from backend.api.deps import ApiError, not_found
from backend.db import (
    agent_runs,
    approvals,
    artifacts,
    defense_recommendations,
    finding_records,
    findings,
    incidents,
    memberships,
    monitoring_events,
    patch_candidates,
    verification_results,
)
from backend.services import project_org
from shared.audit import ActorType
from shared.base import utcnow
from shared.errors import ErrorCode
from shared.ids import IdPrefix, new_id
from shared.incident import (
    INCIDENT_TERMINAL,
    STATE_CSF,
    Incident,
    IncidentAction,
    IncidentCreate,
    IncidentTimelineEntry,
)
from shared.incident import IncidentActionKind as K
from shared.incident import IncidentState as S
from shared.incident import IncidentTimelineAction as T
from standards.incident import IncidentRuleError, apply_action, open_incident


def fail(message: str, *, permission: bool = False) -> NoReturn:
    raise ApiError(
        ErrorCode.APPROVAL_REQUIRED if permission else ErrorCode.CONFLICT_STATE,
        message,
        403 if permission else 409,
    )


def load(conn: Connection, incident_id: str, *, lock: bool = False) -> Incident:
    q = sa.select(incidents.c.doc).where(incidents.c.id == incident_id)
    doc = conn.execute(q.with_for_update() if lock else q).scalar()
    if doc is None:
        raise not_found("incident")
    return Incident.model_validate(doc)


def save(conn: Connection, incident: Incident) -> None:
    conn.execute(
        sa.update(incidents)
        .where(incidents.c.id == incident.id)
        .values(phase=incident.state.value, doc=incident.model_dump(mode="json"))
    )


def _entry(
    conn: Connection,
    incident: Incident,
    actor_id: str,
    action: T,
    note: str,
    before: S | None,
    *,
    system: bool = False,
    evidence=None,
    csf_refs: list[str] | None = None,
) -> Incident:
    ev = audit.record(
        conn,
        org_id=project_org(conn, incident.project_id),
        project_id=incident.project_id,
        actor_type=ActorType.system if system else ActorType.user,
        actor_id=actor_id,
        action=f"incident.{action.value}",
        subject_type="incident",
        subject_id=incident.id,
        details={"from_state": before, "to_state": incident.state, "simulated": incident.simulated},
    )
    entry = IncidentTimelineEntry(
        at=ev.at,
        actor="system" if system else f"user:{actor_id}",
        action=action,
        from_state=before,
        to_state=incident.state,
        note=note,
        csf_refs=list(STATE_CSF[incident.state][1]) if csf_refs is None else csf_refs,
        evidence=evidence or [],
        audit_event_id=ev.id,
    )
    return incident.model_copy(update={"timeline": [*incident.timeline, entry]})


def _links(
    conn: Connection, project_id: str, events, finding_ids, recommendations, verifications=()
) -> bool:
    simulated = False
    for table, ids in (
        (monitoring_events, events),
        (findings, finding_ids),
        (defense_recommendations, recommendations),
    ):
        for ident in ids:
            doc = conn.execute(
                sa.select(table.c.doc).where(table.c.id == ident, table.c.project_id == project_id)
            ).scalar()
            if doc is None:
                raise not_found("incident linked record")
            simulated = simulated or bool(doc.get("simulated") or doc.get("simulation_derived"))
    for ident in verifications:
        row = conn.execute(
            sa.select(findings.c.id)
            .select_from(verification_results)
            .join(patch_candidates, patch_candidates.c.id == verification_results.c.patch_id)
            .join(findings, findings.c.id == patch_candidates.c.finding_id)
            .where(verification_results.c.id == ident, findings.c.project_id == project_id)
        ).first()
        if row is None:
            raise not_found("incident verification")
    return simulated


def create(
    conn: Connection, project_id: str, body: IncidentCreate, actor_id: str, *, system: bool = False
) -> Incident:
    simulated = (
        _links(
            conn, project_id, body.monitoring_event_ids, body.finding_ids, body.recommendation_ids
        )
        or body.simulated
    )
    incident = open_incident(
        body,
        incident_id=new_id(IdPrefix.inc),
        project_id=project_id,
        opened_by="system" if system else f"user:{actor_id}",
        now=utcnow(),
        simulated=simulated,
    )
    initial = incident.timeline[0]
    incident = _entry(
        conn,
        incident.model_copy(update={"timeline": []}),
        actor_id,
        T.reported,
        initial.note,
        None,
        system=system,
    )
    conn.execute(
        sa.insert(incidents).values(
            id=incident.id,
            project_id=project_id,
            phase=incident.state.value,
            doc=incident.model_dump(mode="json"),
        )
    )
    return incident


def _verified(conn: Connection, incident: Incident) -> frozenset[str]:
    rows = conn.execute(
        sa.select(
            verification_results.c.doc,
            patch_candidates.c.finding_id,
            patch_candidates.c.doc.label("patch_doc"),
        )
        .join(patch_candidates, patch_candidates.c.id == verification_results.c.patch_id)
        .where(
            verification_results.c.id.in_(incident.verification_ids),
            verification_results.c.verdict == "accepted",
            patch_candidates.c.finding_id.in_(incident.finding_ids),
        )
    ).all()
    for row in rows:
        vrun = conn.execute(
            sa.select(agent_runs).where(
                agent_runs.c.id == row.doc["produced_by_run_id"], agent_runs.c.agent == "verify"
            )
        )
        run = vrun.mappings().first()
        assessment = conn.execute(
            sa.select(findings.c.assessment_id).where(findings.c.id == row.finding_id)
        ).scalar()
        # Security approvals name the persisted remediation plan; reviewer approvals
        # name the finding directly. Both must belong to this finding/assessment.
        plan_ids = list(
            conn.execute(
                sa.select(finding_records.c.id).where(
                    finding_records.c.finding_id == row.finding_id,
                    finding_records.c.record_type == "remediation_plan",
                )
            ).scalars()
        )
        remediation = conn.execute(
            sa.select(approvals.c.id).where(
                approvals.c.project_id == incident.project_id,
                approvals.c.subject_type == "remediation",
                approvals.c.subject_id.in_([row.finding_id, *plan_ids]),
                approvals.c.assessment_id == assessment,
                approvals.c.status == "approved",
            )
        ).scalar()
        if (
            run
            and run["status"] == "succeeded"
            and run["assessment_id"] == assessment
            and remediation
            and row.doc["produced_by_run_id"] != row.patch_doc["produced_by_run_id"]
        ):
            return frozenset({row.doc["id"]})
    fail("accepted independent Verify and approved remediation for linked finding required")


def _evidence(conn: Connection, incident: Incident, refs, *, regression: bool = False) -> None:
    fortify = {
        d.get("proposed_test_artifact_id")
        for d in conn.execute(
            sa.select(finding_records.c.doc).where(
                finding_records.c.finding_id.in_(incident.finding_ids),
                finding_records.c.record_type == "hardening",
            )
        ).scalars()
    }
    fortify.discard(None)
    for ref in refs:
        if regression and not (ref.artifact_id and ref.sha256):
            fail("regression evidence requires a persisted artifact and matching hash")
        if ref.artifact_id:
            stored = conn.execute(
                sa.select(artifacts.c.id).where(
                    artifacts.c.id == ref.artifact_id,
                    artifacts.c.project_id == incident.project_id,
                    artifacts.c.sha256 == ref.sha256,
                )
            ).scalar()
            if stored is None:
                fail("evidence must reference a persisted project artifact with matching hash")
        if regression and ref.artifact_id not in fortify:
            fail("lessons evidence must cite a persisted Fortify regression artifact")


def act(conn: Connection, incident: Incident, body: IncidentAction, user_id: str) -> Incident:
    """Canonical pure rules plus database relationship and executed-evidence checks."""
    _evidence(conn, incident, body.evidence)
    simulated = incident.simulated
    if body.kind is K.assign_owner and body.owner:
        if (
            conn.execute(
                sa.select(memberships.c.user_id).where(
                    memberships.c.org_id == project_org(conn, incident.project_id),
                    memberships.c.user_id == body.owner,
                )
            ).scalar()
            is None
        ):
            raise not_found("incident owner")
    if body.kind is K.link:
        simulated = (
            _links(
                conn,
                incident.project_id,
                body.monitoring_event_ids,
                body.finding_ids,
                body.recommendation_ids,
                body.verification_ids,
            )
            or simulated
        )
    if body.kind is K.record_lessons_learned:
        _evidence(conn, incident, body.evidence, regression=True)
    accepted: frozenset[str] = frozenset()
    if body.kind is K.transition and body.target_state is S.eradication:
        accepted = _verified(conn, incident)
    # Pure lifecycle rules cannot query project membership, artifact hashes or Verify
    # producer provenance. Resolve those from persisted records before applying them.
    try:
        updated, entry = apply_action(
            incident,
            body,
            actor_user_id=user_id,
            actor_role="owner",
            now=utcnow(),
            accepted_verification_ids=accepted,
        )
    except IncidentRuleError as exc:
        code = ErrorCode(exc.code)
        status = (
            403
            if code in (ErrorCode.FORBIDDEN, ErrorCode.APPROVAL_REQUIRED)
            else (
                404
                if code is ErrorCode.NOT_FOUND
                else 409
                if code is ErrorCode.CONFLICT_STATE
                else 422
            )
        )
        raise ApiError(code, exc.message, status) from exc
    updated = updated.model_copy(update={"simulated": simulated, "timeline": updated.timeline[:-1]})
    updated = _entry(
        conn,
        updated,
        user_id,
        entry.action,
        entry.note,
        entry.from_state or incident.state,
        evidence=entry.evidence,
        csf_refs=entry.csf_refs,
    )
    save(conn, updated)
    return updated


def correlate_anomaly(
    conn: Connection, event, finding_ids: list[str], route: str
) -> Incident | None:
    linked = list(
        conn.execute(
            sa.select(findings.c.id).where(
                findings.c.id.in_(finding_ids),
                findings.c.project_id == event.project_id,
                findings.c.kind == "security",
                findings.c.status.in_(
                    ["validated", "diagnosed", "patch_proposed", "patch_rejected", "unresolved"]
                ),
            )
        ).scalars()
    )
    if not linked:
        return None
    from backend.db import projects

    conn.execute(
        sa.select(projects.c.id).where(projects.c.id == event.project_id).with_for_update()
    )
    for doc in conn.execute(
        sa.select(incidents.c.doc)
        .where(incidents.c.project_id == event.project_id)
        .with_for_update()
    ).scalars():
        existing = Incident.model_validate(doc)
        if existing.state not in INCIDENT_TERMINAL and set(existing.finding_ids) & set(linked):
            updated = existing.model_copy(
                update={
                    "monitoring_event_ids": list(
                        dict.fromkeys([*existing.monitoring_event_ids, event.id])
                    ),
                    "simulated": existing.simulated or bool(getattr(event, "simulated", True)),
                }
            )
            updated = _entry(
                conn,
                updated,
                "runtime-correlation",
                T.evidence_linked,
                "Additional runtime anomaly; no automatic incident declaration",
                existing.state,
                system=True,
            )
            save(conn, updated)
            return updated
    return create(
        conn,
        event.project_id,
        IncidentCreate(
            title=f"Reported runtime anomaly: {route}"[:500],
            simulated=bool(getattr(event, "simulated", True)),
            monitoring_event_ids=[event.id],
            finding_ids=linked,
            note="Threshold crossed with validated finding context; human triage required",
        ),
        "runtime-correlation",
        system=True,
    )
