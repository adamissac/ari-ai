"""AssessmentHost — the persistence + gate API that runtime agents use.

The security-agents orchestrator (Alan) and the code reviewer (Sai) never write the
database directly. They receive an ``AssessmentHost`` and call it to transition
state, open/close AgentRuns, record findings, patches, Verify verdicts and
approvals, store artifacts and charge LLM usage. Deterministic gates live here,
independent of any prompt:

* state transitions must be legal (``shared.assessment.ALLOWED_TRANSITIONS``);
* the scope must be active/unexpired before work and at every transition;
* budget (tokens / USD / wall clock) is enforced on every charge;
* cancellation is observed at every call;
* a VerificationResult must come from a ``verify`` AgentRun that is not the run
  that produced the patch (Verify independence);
* REMEDIATION is only reachable through an approved ``remediation`` approval.

Integration contract (published V0, see coordination message):

    class Orchestrator(Protocol):
        def run(self, host: AssessmentHost) -> None: ...

``settings.orchestrator_factory`` names a ``module:callable`` returning one. The
worker calls ``run`` for a fresh assessment and again after an approval decision
(``host.assessment.state == AWAITING_APPROVAL``).
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.engine import Connection

from backend import audit
from backend.artifacts import ArtifactStore
from backend.db import (
    agent_runs,
    approvals,
    assessment_events,
    assessments,
    authorized_scopes,
    finding_records,
    findings,
    patch_candidates,
    projects,
    transaction,
    verification_results,
)
from shared.assessment import (
    TERMINAL_STATES,
    AgentName,
    AgentRun,
    AgentRunStatus,
    Assessment,
    AssessmentState,
    ToolCallRecord,
    can_transition,
)
from shared.audit import ActorType
from shared.base import utcnow
from shared.errors import ErrorBody, ErrorCode
from shared.events import StreamEvent, StreamEventType
from shared.evidence import ArtifactKind, ArtifactRef, EvidenceKind
from shared.findings import (
    AttackPath,
    Finding,
    HardeningRecommendation,
    Hypothesis,
    PatchCandidate,
    RemediationPlan,
    RootCause,
    ValidationResult,
    VerificationResult,
)
from shared.ids import IdPrefix, new_id
from shared.scope import Approval, ApprovalStatus, ApprovalSubject, AuthorizedScope, ScopeStatus
from shared.tenancy import Usage


class HostError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class Orchestrator(Protocol):
    def run(self, host: AssessmentHost) -> None: ...


_RECORD_TYPES: dict[type[BaseModel], str] = {
    Hypothesis: "hypothesis",
    ValidationResult: "validation_result",
    AttackPath: "attack_path",
    RootCause: "root_cause",
    RemediationPlan: "remediation_plan",
    HardeningRecommendation: "hardening",
}


def _emit(
    conn: Connection, assessment_id: str, etype: StreamEventType, message: str, **fields: Any
) -> StreamEvent:
    seq = conn.execute(
        sa.update(assessments)
        .where(assessments.c.id == assessment_id)
        .values(event_seq=assessments.c.event_seq + 1)
        .returning(assessments.c.event_seq)
    ).scalar_one()
    ev = StreamEvent(
        seq=seq,
        assessment_id=assessment_id,
        type=etype,
        message=message[:500],
        at=utcnow(),
        **fields,
    )
    conn.execute(
        sa.insert(assessment_events).values(
            assessment_id=assessment_id, seq=seq, type=etype.value, doc=ev.model_dump(mode="json")
        )
    )
    conn.execute(sa.text("SELECT pg_notify('assessment_events', :id)"), {"id": assessment_id})
    return ev


def emit_event(
    conn: Connection, assessment_id: str, etype: StreamEventType, message: str, **fields: Any
) -> StreamEvent:
    return _emit(conn, assessment_id, etype, message, **fields)


def scope_problem(scope: AuthorizedScope, repo_id: str) -> str | None:
    if scope.status is not ScopeStatus.active:
        return f"scope {scope.id} is {scope.status.value}"
    if scope.expires_at <= utcnow():
        return f"scope {scope.id} expired at {scope.expires_at.isoformat()}"
    if not any(t.repo_id == repo_id for t in scope.targets):
        return f"scope {scope.id} does not cover repository {repo_id}"
    return None


class AssessmentHost:
    def __init__(
        self, assessment_id: str, *, job_ctx: Any | None = None, store: ArtifactStore | None = None
    ) -> None:
        self.assessment_id = assessment_id
        self._job_ctx = job_ctx
        self.store = store or ArtifactStore()
        self._started_monotonic = time.monotonic()
        with transaction() as conn:
            row = self._row(conn)
            self.project_id: str = row["project_id"]
            self.repo_id: str = row["repo_id"]
            self.org_id: str = conn.execute(
                sa.select(projects.c.org_id).where(projects.c.id == self.project_id)
            ).scalar_one()

    # ------------------------------------------------------------------ reads
    def _row(self, conn: Connection, *, lock: bool = False) -> dict[str, Any]:
        q = sa.select(assessments).where(assessments.c.id == self.assessment_id)
        if lock:
            q = q.with_for_update()
        row = conn.execute(q).mappings().first()
        if row is None:
            raise HostError(ErrorCode.NOT_FOUND, f"assessment {self.assessment_id} not found")
        return dict(row)

    @property
    def assessment(self) -> Assessment:
        with transaction() as conn:
            return Assessment.model_validate(self._row(conn)["doc"])

    @property
    def scope(self) -> AuthorizedScope:
        with transaction() as conn:
            doc = conn.execute(
                sa.select(authorized_scopes.c.doc).where(
                    authorized_scopes.c.id == self.assessment.scope_id
                )
            ).scalar_one()
        return AuthorizedScope.model_validate(doc)

    def approvals(self) -> list[Approval]:
        with transaction() as conn:
            docs = conn.execute(
                sa.select(approvals.c.doc)
                .where(approvals.c.assessment_id == self.assessment_id)
                .order_by(approvals.c.created_at)
            ).scalars()
            return [Approval.model_validate(d) for d in docs]

    def findings(self) -> list[Finding]:
        with transaction() as conn:
            docs = conn.execute(
                sa.select(findings.c.doc)
                .where(findings.c.assessment_id == self.assessment_id)
                .order_by(findings.c.created_at)
            ).scalars()
            return [Finding.model_validate(d) for d in docs]

    # ------------------------------------------------------------------ gates
    def check_cancelled(self) -> None:
        if self._job_ctx is not None:
            self._job_ctx.check_cancelled()
        with transaction() as conn:
            if self._row(conn)["cancel_requested"]:
                raise HostError(ErrorCode.CANCELLED, "assessment cancellation requested")

    def require_active_scope(self) -> AuthorizedScope:
        scope = self.scope
        problem = scope_problem(scope, self.repo_id)
        if problem:
            raise HostError(ErrorCode.SCOPE_DENIED, problem)
        return scope

    def _budget_problem(self, a: Assessment) -> str | None:
        b, u = a.budget, a.usage
        if u.input_tokens + u.output_tokens > b.max_tokens:
            return f"token budget {b.max_tokens} exceeded"
        if u.usd > b.max_usd:
            return f"USD budget {b.max_usd} exceeded"
        if time.monotonic() - self._started_monotonic > b.max_wall_clock_s:
            return f"wall-clock budget {b.max_wall_clock_s}s exceeded"
        return None

    def ensure_budget(self) -> None:
        problem = self._budget_problem(self.assessment)
        if problem:
            self.terminate(AssessmentState.BUDGET_EXHAUSTED, ErrorCode.BUDGET_EXHAUSTED, problem)
            raise HostError(ErrorCode.BUDGET_EXHAUSTED, problem)

    def charge(self, usage: Usage) -> None:
        """Add usage to the assessment total; enforces the budget afterwards."""
        with transaction() as conn:
            row = self._row(conn, lock=True)
            a = Assessment.model_validate(row["doc"])
            total = a.usage.model_copy(
                update={k: getattr(a.usage, k) + getattr(usage, k) for k in Usage.model_fields}
            )
            a = a.model_copy(update={"usage": total, "updated_at": utcnow()})
            conn.execute(
                sa.update(assessments)
                .where(assessments.c.id == self.assessment_id)
                .values(doc=a.model_dump(mode="json"), updated_at=sa.func.now())
            )
        self.ensure_budget()

    # ------------------------------------------------------------- transitions
    def transition(self, target: AssessmentState, message: str = "") -> Assessment:
        self.check_cancelled()
        if target not in TERMINAL_STATES:
            self.require_active_scope()
        if target is AssessmentState.REMEDIATION and not any(
            ap.subject_type is ApprovalSubject.remediation and ap.status is ApprovalStatus.approved
            for ap in self.approvals()
        ):
            raise HostError(
                ErrorCode.APPROVAL_REQUIRED, "REMEDIATION requires an approved remediation approval"
            )
        return self._set_state(target, message or f"state -> {target.value}")

    def terminate(
        self, target: AssessmentState, code: ErrorCode | None, message: str
    ) -> Assessment:
        if target not in TERMINAL_STATES:
            raise ValueError("terminate() requires a terminal state")
        error = ErrorBody(code=code, message=message[:500]) if code else None
        return self._set_state(target, message, error=error)

    def _set_state(
        self, target: AssessmentState, message: str, error: ErrorBody | None = None
    ) -> Assessment:
        with transaction() as conn:
            row = self._row(conn, lock=True)
            a = Assessment.model_validate(row["doc"])
            if a.state is target:
                return a
            if not can_transition(a.state, target):
                raise HostError(
                    ErrorCode.CONFLICT_STATE,
                    f"illegal transition {a.state.value} -> {target.value}",
                )
            now = utcnow()
            update: dict[str, Any] = {"state": target, "updated_at": now}
            if target in TERMINAL_STATES:
                update["completed_at"] = now
            if error is not None:
                update["error"] = error
            new = a.model_copy(update=update)
            conn.execute(
                sa.update(assessments)
                .where(assessments.c.id == self.assessment_id)
                .values(
                    state=target.value, doc=new.model_dump(mode="json"), updated_at=sa.func.now()
                )
            )
            _emit(
                conn,
                self.assessment_id,
                StreamEventType.state_changed,
                message,
                state=target,
                data={"from": a.state.value, **({"error_code": error.code.value} if error else {})},
            )
            if target is AssessmentState.COMPLETED:
                _emit(
                    conn,
                    self.assessment_id,
                    StreamEventType.completed,
                    "assessment completed",
                    state=target,
                )
            elif target in TERMINAL_STATES:
                _emit(
                    conn,
                    self.assessment_id,
                    StreamEventType.failed,
                    message,
                    state=target,
                    data={"error_code": error.code.value if error else None},
                )
            audit.record(
                conn,
                org_id=self.org_id,
                project_id=self.project_id,
                actor_type=ActorType.system,
                actor_id="orchestrator",
                action="assessment.state_changed",
                subject_type="assessment",
                subject_id=self.assessment_id,
                details={"from": a.state.value, "to": target.value},
            )
            return new

    def progress(self, message: str, *, agent: AgentName | None = None, **data: Any) -> None:
        with transaction() as conn:
            _emit(
                conn,
                self.assessment_id,
                StreamEventType.progress,
                message,
                state=AssessmentState(self._row(conn)["state"]),
                agent=agent,
                data=data,
            )

    # --------------------------------------------------------------------- llm
    def llm(self) -> Any:
        """LLM gateway bound to this assessment's budget, usage ledger and cancellation."""
        from backend.llm import build_gateway

        return build_gateway(
            charge=self.charge,
            ensure_budget=self.ensure_budget,
            check_cancelled=self.check_cancelled,
        )

    # --------------------------------------------------------------- artifacts
    def store_json(self, value: Any, kind: ArtifactKind = ArtifactKind.tool_output) -> ArtifactRef:
        with transaction() as conn:
            return self.store.put_json(conn, value, kind=kind, project_id=self.project_id)

    def store_text(
        self, text: str, kind: ArtifactKind = ArtifactKind.log, media_type: str = "text/plain"
    ) -> ArtifactRef:
        with transaction() as conn:
            return self.store.put_text(
                conn, text, kind=kind, project_id=self.project_id, media_type=media_type
            )

    # -------------------------------------------------------------- agent runs
    def start_agent_run(
        self,
        agent: AgentName,
        step_key: str,
        *,
        attempt: int = 1,
        provider_mode: str,
        model_id: str | None,
        prompt_version: str | None,
        input_payload: Any | None = None,
    ) -> str:
        self.check_cancelled()
        self.ensure_budget()
        run_id = new_id(IdPrefix.run)
        input_ref = (
            self.store_json(input_payload, ArtifactKind.other)
            if input_payload is not None
            else None
        )
        run = AgentRun(
            id=run_id,
            assessment_id=self.assessment_id,
            agent=agent,
            step_key=step_key,
            attempt=attempt,
            status=AgentRunStatus.running,
            provider_mode=provider_mode,
            model_id=model_id,
            prompt_version=prompt_version,
            input_artifact_id=input_ref.id if input_ref else None,
            started_at=utcnow(),
        )
        with transaction() as conn:
            conn.execute(
                sa.insert(agent_runs).values(
                    id=run_id,
                    assessment_id=self.assessment_id,
                    agent=agent.value,
                    status=run.status.value,
                    doc=run.model_dump(mode="json"),
                )
            )
            _emit(
                conn,
                self.assessment_id,
                StreamEventType.agent_run_started,
                f"{agent.value} started {step_key}",
                agent=agent,
                agent_run_id=run_id,
                state=AssessmentState(self._row(conn)["state"]),
            )
        return run_id

    def finish_agent_run(
        self,
        run_id: str,
        status: AgentRunStatus,
        *,
        usage: Usage | None = None,
        tool_calls: list[ToolCallRecord] | None = None,
        output: Any | None = None,
        transcript: Any | None = None,
        error: ErrorBody | None = None,
    ) -> AgentRun:
        out_ref = self.store_json(output, ArtifactKind.other) if output is not None else None
        tr_ref = (
            self.store_json(transcript, ArtifactKind.llm_transcript)
            if transcript is not None
            else None
        )
        with transaction() as conn:
            doc = conn.execute(
                sa.select(agent_runs.c.doc).where(agent_runs.c.id == run_id).with_for_update()
            ).scalar_one()
            run = AgentRun.model_validate(doc)
            if run.status is not AgentRunStatus.running:
                raise HostError(
                    ErrorCode.CONFLICT_STATE, f"agent run {run_id} already {run.status.value}"
                )
            run = run.model_copy(
                update={
                    "status": status,
                    "usage": usage or run.usage,
                    "tool_calls": tool_calls or run.tool_calls,
                    "output_artifact_id": out_ref.id if out_ref else None,
                    "transcript_artifact_id": tr_ref.id if tr_ref else None,
                    "error": error,
                    "ended_at": utcnow(),
                }
            )
            AgentRun.model_validate(run.model_dump())
            conn.execute(
                sa.update(agent_runs)
                .where(agent_runs.c.id == run_id)
                .values(status=status.value, doc=run.model_dump(mode="json"))
            )
            _emit(
                conn,
                self.assessment_id,
                StreamEventType.agent_run_finished,
                f"{run.agent.value} {status.value}",
                agent=run.agent,
                agent_run_id=run_id,
                data={
                    "usage": run.usage.model_dump(),
                    "error_code": error.code.value if error else None,
                },
            )
        return run

    def agent_run(self, run_id: str) -> AgentRun:
        with transaction() as conn:
            return AgentRun.model_validate(
                conn.execute(
                    sa.select(agent_runs.c.doc).where(agent_runs.c.id == run_id)
                ).scalar_one()
            )

    # --------------------------------------------------------------- findings
    def record_finding(self, finding: Finding, *, actor: str) -> Finding:
        if finding.assessment_id != self.assessment_id:
            raise HostError(ErrorCode.VALIDATION_FAILED, "finding belongs to another assessment")
        paths = sorted(
            {e.path for e in finding.evidence if e.kind is EvidenceKind.source_span and e.path}
        )
        with transaction() as conn:
            existing = conn.execute(
                sa.select(findings.c.doc).where(findings.c.id == finding.id).with_for_update()
            ).scalar()
            if existing is None:
                conn.execute(
                    sa.insert(findings).values(
                        id=finding.id,
                        project_id=self.project_id,
                        assessment_id=self.assessment_id,
                        kind=finding.kind.value,
                        status=finding.status.value,
                        paths=paths,
                        doc=finding.model_dump(mode="json"),
                    )
                )
            else:
                conn.execute(
                    sa.update(findings)
                    .where(findings.c.id == finding.id)
                    .values(
                        status=finding.status.value,
                        paths=paths,
                        doc=finding.model_dump(mode="json"),
                    )
                )
            _emit(
                conn,
                self.assessment_id,
                StreamEventType.finding_updated,
                f"{finding.kind.value} finding {finding.status.value}: {finding.title}",
                finding_id=finding.id,
                data={"status": finding.status.value, "actor": actor},
            )
        return finding

    def record(self, finding_id: str, record: BaseModel) -> None:
        """Persist Hypothesis/ValidationResult/AttackPath/RootCause/RemediationPlan/Hardening."""
        rtype = _RECORD_TYPES.get(type(record))
        if rtype is None:
            raise HostError(
                ErrorCode.VALIDATION_FAILED, f"unsupported record {type(record).__name__}"
            )
        if getattr(record, "finding_id", finding_id) != finding_id:
            raise HostError(ErrorCode.VALIDATION_FAILED, "record finding_id mismatch")
        self._require_own_finding(finding_id)
        with transaction() as conn:
            conn.execute(
                sa.insert(finding_records).values(
                    id=record.id,
                    finding_id=finding_id,
                    record_type=rtype,
                    doc=record.model_dump(mode="json"),
                )
            )

    def _require_own_finding(self, finding_id: str) -> None:
        with transaction() as conn:
            owner = conn.execute(
                sa.select(findings.c.assessment_id).where(findings.c.id == finding_id)
            ).scalar()
        if owner != self.assessment_id:
            raise HostError(ErrorCode.NOT_FOUND, f"finding {finding_id} not in this assessment")

    def record_patch(self, patch: PatchCandidate) -> PatchCandidate:
        self._require_own_finding(patch.finding_id)
        run = self.agent_run(patch.produced_by_run_id)
        if run.assessment_id != self.assessment_id:
            raise HostError(
                ErrorCode.VALIDATION_FAILED, "patch produced by a run of another assessment"
            )
        with transaction() as conn:
            conn.execute(
                sa.insert(patch_candidates).values(
                    id=patch.id, finding_id=patch.finding_id, doc=patch.model_dump(mode="json")
                )
            )
        return patch

    def record_verification(self, result: VerificationResult) -> VerificationResult:
        """Verify independence gate: verdict must come from a distinct, finished verify run."""
        with transaction() as conn:
            pdoc = conn.execute(
                sa.select(patch_candidates.c.doc).where(patch_candidates.c.id == result.patch_id)
            ).scalar()
        if pdoc is None:
            raise HostError(ErrorCode.NOT_FOUND, f"patch {result.patch_id} not found")
        patch = PatchCandidate.model_validate(pdoc)
        self._require_own_finding(patch.finding_id)
        vrun = self.agent_run(result.produced_by_run_id)
        if vrun.agent is not AgentName.verify:
            raise HostError(
                ErrorCode.FORBIDDEN, "VerificationResult must be produced by the verify agent"
            )
        if vrun.id == patch.produced_by_run_id or vrun.assessment_id != self.assessment_id:
            raise HostError(
                ErrorCode.FORBIDDEN, "Verify must run independently of the patch-producing run"
            )
        if not any(c.evidence for c in result.checks):
            raise HostError(
                ErrorCode.VALIDATION_FAILED, "verification checks need executed evidence"
            )
        with transaction() as conn:
            conn.execute(
                sa.insert(verification_results).values(
                    id=result.id,
                    patch_id=result.patch_id,
                    verdict=result.verdict.value,
                    doc=result.model_dump(mode="json"),
                )
            )
        return result

    # --------------------------------------------------------------- approvals
    def request_approval(
        self, subject_type: ApprovalSubject, subject_id: str, reason: str
    ) -> Approval:
        ap = Approval(
            id=new_id(IdPrefix.apv),
            project_id=self.project_id,
            subject_type=subject_type,
            subject_id=subject_id,
            status=ApprovalStatus.pending,
            requested_at=utcnow(),
            reason=reason,
        )
        with transaction() as conn:
            conn.execute(
                sa.insert(approvals).values(
                    id=ap.id,
                    project_id=self.project_id,
                    subject_type=subject_type.value,
                    subject_id=subject_id,
                    assessment_id=self.assessment_id,
                    status=ap.status.value,
                    doc=ap.model_dump(mode="json"),
                )
            )
            _emit(
                conn,
                self.assessment_id,
                StreamEventType.approval_requested,
                f"approval requested: {subject_type.value} {subject_id}",
                approval_id=ap.id,
            )
            audit.record(
                conn,
                org_id=self.org_id,
                project_id=self.project_id,
                actor_type=ActorType.system,
                actor_id="orchestrator",
                action="approval.requested",
                subject_type="approval",
                subject_id=ap.id,
                details={"subject_type": subject_type.value, "subject_id": subject_id},
            )
        return ap


def input_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


@contextmanager
def agent_run(host: AssessmentHost, agent: AgentName, step_key: str, **kw: Any) -> Iterator[str]:
    """Convenience: open a run, mark failed on exception."""
    run_id = host.start_agent_run(agent, step_key, **kw)
    try:
        yield run_id
    except HostError as exc:
        host.finish_agent_run(
            run_id, AgentRunStatus.failed, error=ErrorBody(code=exc.code, message=str(exc)[:500])
        )
        raise
    except Exception as exc:
        host.finish_agent_run(
            run_id,
            AgentRunStatus.failed,
            error=ErrorBody(code=ErrorCode.INTERNAL, message=f"{type(exc).__name__}: {exc}"[:500]),
        )
        raise
