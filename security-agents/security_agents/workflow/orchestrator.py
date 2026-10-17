"""Deterministic orchestrator: runs one assessment through the seven agents.

The orchestrator owns state, gates and artifacts; agents own role reasoning.
Every step is idempotent by `(assessment_id, step_key, attempt)`, every
transition is logged write-ahead, and every gate (scope, approval, budget, kill
switch) is evaluated here in code — never inside an agent.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import standards_bridge
from ..agents import diagnose as diagnose_agent
from ..agents import fortify as fortify_agent
from ..agents import patch as patch_agent
from ..agents import probe as probe_agent
from ..agents import scout as scout_agent
from ..agents import trace as trace_agent
from ..agents import verify as verify_agent
from ..checks.library import CheckLibrary
from ..contracts import (
    AgentName,
    AgentRun,
    Approval,
    AttackPath,
    AuditEvent,
    AuthorizedScope,
    Budget,
    ErrorCode,
    EvidenceRef,
    HardeningRecommendation,
    Hypothesis,
    HypothesisDraft,
    PatchCandidate,
    PlatformError,
    RegressionTest,
    RemediationPlan,
    RootCause,
    SeverityAssessment,
    Usage,
    ValidationOutcome,
    ValidationResult,
    VerificationResult,
    new_id,
    utcnow,
)
from ..intel import CodeIntel, FindingsHistory, hypothesis_key
from ..llm import LLMGateway
from ..runtime import AgentSpec, StepOutcome, StepRecord, run_agent
from ..sandbox.driver import SandboxDriver
from ..scope_guard import ActionRequest
from ..scope_guard import check as scope_check
from ..tools import (
    AuditSink,
    CheckRunner,
    PatchApplier,
    PatchWorktree,
    TestRunner,
    ToolContext,
    ToolRegistry,
    default_registry,
    recipe_from_snapshot,
)
from .states import (
    AssessmentState,
    RemediationState,
    StateLog,
    next_remediation_state,
    transition,
)

DEFAULT_BUDGET = Budget(max_tokens=400_000, max_usd=8.0, max_wall_clock_s=3600.0)


class ApprovalPending(Exception):
    """Raised by an approval callback when a human decision is outstanding.

    The orchestrator stops in `AWAITING_APPROVAL` without a terminal
    transition, so a host can persist the request and re-enter later.
    """

    def __init__(self, finding_id: str, approval_id: str | None = None) -> None:
        super().__init__(f"approval pending for {finding_id}")
        self.finding_id = finding_id
        self.approval_id = approval_id


class AssessmentSink:
    """Hooks a host uses to mirror orchestration into its own store.

    Every method is a no-op by default, so the standalone orchestrator behaves
    exactly as before. A host implementation (see `security_agents.host_adapter`)
    persists each record and emits progress events.
    """

    def on_transition(self, src: AssessmentState, dst: AssessmentState, note: str) -> None: ...

    def on_finding(self, finding: FindingRecord) -> None: ...

    def on_record(self, finding: FindingRecord, record: Any, kind: str) -> None: ...

    def on_patch(self, finding: FindingRecord, candidate: PatchCandidate, diff: str) -> None: ...

    def on_verification(self, finding: FindingRecord, result: VerificationResult) -> None: ...

    def on_status(self, finding: FindingRecord, status: str) -> None: ...

    def on_standards(self, finding: FindingRecord) -> None: ...


@dataclass
class FindingRecord:
    """Everything the platform knows about one security finding."""

    finding_id: str
    hypothesis: Hypothesis
    status: str = "hypothesis"
    validation: ValidationResult | None = None
    attack_path: AttackPath | None = None
    severity: SeverityAssessment | None = None
    root_cause: RootCause | None = None
    plan: RemediationPlan | None = None
    related_sites: list[EvidenceRef] = field(default_factory=list)
    approval: Approval | None = None
    candidates: list[PatchCandidate] = field(default_factory=list)
    verifications: list[VerificationResult] = field(default_factory=list)
    regression_tests: list[RegressionTest] = field(default_factory=list)
    recommendations: list[HardeningRecommendation] = field(default_factory=list)
    future_hypotheses: list[HypothesisDraft] = field(default_factory=list)
    monitoring_hints: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    standards: Any = None  # shared.standards.FindingStandards

    def public(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "title": self.hypothesis.title,
            "weakness_class": self.hypothesis.weakness_class,
            "status": self.status,
            "severity": self.severity.level.value if self.severity else None,
            "validation_outcome": self.validation.outcome.value if self.validation else None,
            "verdicts": [v.verdict for v in self.verifications],
            "regression_tests": [t.test_path for t in self.regression_tests],
            "notes": self.notes,
            "standards": standards_bridge.summary(self.standards),
        }


@dataclass
class AssessmentResult:
    assessment_id: str
    state: AssessmentState
    state_log: StateLog
    runs: list[AgentRun] = field(default_factory=list)
    records: list[StepRecord] = field(default_factory=list)
    findings: list[FindingRecord] = field(default_factory=list)
    audit: list[AuditEvent] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    error_code: ErrorCode | None = None
    error_detail: str | None = None

    def runs_by_agent(self) -> dict[str, list[AgentRun]]:
        out: dict[str, list[AgentRun]] = {}
        for r in self.runs:
            out.setdefault(r.agent.value, []).append(r)
        return out

    def agents_executed(self) -> set[str]:
        return {r.agent.value for r in self.runs}

    def report(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "state": self.state.value,
            "states": self.state_log.states(),
            "provider_modes": sorted({r.provider_mode for r in self.runs}),
            "agents_executed": sorted(self.agents_executed()),
            "runs": [
                {
                    "agent": r.agent.value,
                    "step_key": r.step_key,
                    "attempt": r.attempt,
                    "status": r.status,
                    "model_id": r.model_id,
                    "provider_mode": r.provider_mode,
                    "tool_calls": r.tool_calls,
                    "llm_turns": r.llm_turns,
                    "tokens": r.usage.total_tokens,
                    "usd": round(r.usage.usd, 6),
                    "error_code": r.error_code.value if r.error_code else None,
                }
                for r in self.runs
            ],
            "findings": [f.public() for f in self.findings],
            "usage": self.usage.model_dump(mode="json"),
            "audit_actions": [e.action for e in self.audit],
            "error_code": self.error_code.value if self.error_code else None,
            "error_detail": self.error_detail,
        }


@dataclass
class OrchestratorConfig:
    assessment_id: str
    project_id: str
    org_id: str
    scope: AuthorizedScope
    target_id: str
    requested_by: str
    budget: Budget = field(default_factory=lambda: DEFAULT_BUDGET)
    max_hypotheses_to_validate: int = 3
    max_hypotheses: int = 5
    org_member_count: int = 1
    protected_tests: list[str] = field(default_factory=list)
    test_command_args: tuple[str, ...] = ("-q", "tests")


class Orchestrator:
    """Runs the assessment. All gates live in this class, in plain Python."""

    def __init__(
        self,
        config: OrchestratorConfig,
        *,
        intel: CodeIntel,
        gateway: LLMGateway,
        driver: SandboxDriver,
        library: CheckLibrary,
        workdir: Path,
        registry: ToolRegistry | None = None,
        history: FindingsHistory | None = None,
        approve_remediation: Callable[[FindingRecord], Approval | None] | None = None,
        sink: AssessmentSink | None = None,
        step_runner: Callable[..., StepOutcome] | None = None,
        kill_switch: Callable[[], bool] = lambda: False,
        cancelled: Callable[[], bool] = lambda: False,
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self.config = config
        self.intel = intel
        self.gateway = gateway
        self.driver = driver
        self.library = library
        self.workdir = workdir
        self.registry = registry or default_registry()
        self.history = history or FindingsHistory()
        self.approve_remediation = approve_remediation
        self.sink = sink or AssessmentSink()
        # Injected so a backend host can run the agent turn through its own
        # gateway instead of this package's provider (ADR-0007: one gateway).
        self.step_runner = step_runner
        self.kill_switch = kill_switch
        self.cancelled = cancelled
        self.now = now

        self.state = AssessmentState.CREATED
        self.state_log = StateLog()
        self.result = AssessmentResult(
            assessment_id=config.assessment_id, state=self.state, state_log=self.state_log
        )
        self.audit = AuditSink()
        self._patch_artifacts: dict[str, dict[str, Any]] = {}
        self._completed_steps: dict[str, StepOutcome] = {}
        self._audit_prev_hash = "0" * 64
        self._baseline_failing: list[str] = []
        self.workdir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ plumbing

    def _goto(self, dst: AssessmentState, note: str = "") -> None:
        src = self.state
        self.state = transition(src, dst)
        self.state_log.record(src, dst, note)
        self.result.state = self.state
        self.sink.on_transition(src, dst, note)
        self._audit(
            "assessment.transition",
            "assessment",
            self.config.assessment_id,
            actor="system",
            src=src.value,
            dst=dst.value,
            note=note,
        )

    def _audit(
        self, action: str, subject_type: str, subject_id: str, *, actor: str = "system", **details: Any
    ) -> AuditEvent:
        payload = {
            "org_id": self.config.org_id,
            "project_id": self.config.project_id,
            "actor": actor,
            "actor_id": details.pop("actor_id", "system"),
            "action": action,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "at": self.now(),
            "details": details,
        }
        body = json.dumps(
            {**payload, "at": payload["at"].isoformat(), "prev_hash": self._audit_prev_hash},
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(body.encode()).hexdigest()
        event = AuditEvent(**payload, prev_hash=self._audit_prev_hash, hash=digest)  # type: ignore[arg-type]
        self._audit_prev_hash = digest
        self.result.audit.append(event)
        return event

    def _budget_left(self) -> bool:
        return (
            self.result.usage.total_tokens < self.config.budget.max_tokens
            and self.result.usage.usd < self.config.budget.max_usd
        )

    def _context(
        self, agent: AgentName, step_key: str, *, services: dict[str, Any], read_root: Path | None = None
    ) -> ToolContext:
        return ToolContext(
            assessment_id=self.config.assessment_id,
            agent=agent,
            run_id=new_id("run"),
            step_key=step_key,
            read_root=read_root or self.intel.snapshot.root,
            services=services,
            scope=self.config.scope,
            org_member_count=self.config.org_member_count,
            audit=self.audit,
            kill_switch=self.kill_switch,
            now=self.now,
        )

    def _read_services(self) -> dict[str, Any]:
        return {"intel": self.intel, "history": self.history, "checks": self.library}

    def _run_step(
        self, spec: AgentSpec, ctx: ToolContext, prompt: str, *, input_ref: str, attempt: int = 1
    ) -> StepOutcome:
        """Idempotent agent step. A completed step key is never re-executed."""
        key = f"{ctx.step_key}#{attempt}"
        if key in self._completed_steps:
            return self._completed_steps[key]
        if not self._budget_left():
            raise PlatformError(ErrorCode.BUDGET_EXHAUSTED, "assessment budget exhausted")
        runner = self.step_runner or run_agent
        outcome = runner(
            spec,
            gateway=self.gateway,
            registry=self.registry,
            ctx=ctx,
            task_prompt=prompt,
            budget=self.config.budget,
            assessment_usage=self.result.usage,
            input_ref=input_ref,
            cancelled=self.cancelled,
        )
        outcome.run.attempt = attempt
        self.result.runs.append(outcome.run)
        self.result.records.append(outcome.record)
        self._completed_steps[key] = outcome
        self._audit(
            "agent.step",
            "agent_run",
            outcome.run.id,
            actor="agent",
            actor_id=spec.name.value,
            status=outcome.run.status,
            provider_mode=outcome.run.provider_mode,
            tool_calls=outcome.run.tool_calls,
            error_code=outcome.run.error_code,
        )
        return outcome

    def _fail(self, code: ErrorCode, detail: str) -> AssessmentResult:
        target = (
            AssessmentState.BUDGET_EXHAUSTED
            if code is ErrorCode.BUDGET_EXHAUSTED
            else AssessmentState.CANCELLED
            if code is ErrorCode.CANCELLED
            else AssessmentState.FAILED
        )
        self._goto(target, detail[:200])
        self.result.error_code = code
        self.result.error_detail = detail
        self._audit(
            "assessment.failed", "assessment", self.config.assessment_id, code=code.value, detail=detail[:300]
        )
        return self.result

    # ------------------------------------------------------------------ main

    def run(self) -> AssessmentResult:
        try:
            return self._run()
        except PlatformError as exc:
            return self._fail(exc.code, exc.message)

    def _run(self) -> AssessmentResult:
        cfg = self.config

        # ---- SCOPE_CHECK gate
        self._goto(AssessmentState.SCOPE_CHECK)
        decision = scope_check(
            cfg.scope,
            ActionRequest(action="assessment_start"),
            self.now(),
            org_member_count=cfg.org_member_count,
        )
        self._audit(
            "scope.checked",
            "scope",
            cfg.scope.id,
            allowed=decision.allowed,
            reason_code=decision.reason_code,
        )
        if not decision.allowed:
            return self._fail(ErrorCode.SCOPE_DENIED, f"{decision.reason_code} {decision.detail}".strip())

        # ---- INDEXING (code intelligence is an upstream subsystem)
        self._goto(AssessmentState.INDEXING, self.intel.provenance().get("status", ""))
        if not self.intel.entry_points():
            return self._fail(ErrorCode.SNAPSHOT_NOT_READY, "no entry points in snapshot index")

        # ---- FUNCTIONAL_REVIEW is Sai's pillar; we record the baseline it needs.
        self._goto(AssessmentState.FUNCTIONAL_REVIEW, "baseline test run (code_review pillar pending)")
        self._baseline_failing = self._baseline_test_failures()

        # ---- RECON (Scout)
        self._goto(AssessmentState.RECON)
        hypotheses = self._run_scout()
        if not hypotheses:
            self._goto(AssessmentState.REPORTING, "no hypotheses")
            return self._finish()

        # ---- VALIDATION (Probe, one step per hypothesis, capped)
        self._goto(AssessmentState.VALIDATION)
        confirmed = self._run_validation(hypotheses)
        if not confirmed:
            self._goto(AssessmentState.REPORTING, "no confirmed findings")
            return self._finish()

        # ---- ANALYSIS (Trace)
        self._goto(AssessmentState.ANALYSIS)
        for finding in confirmed:
            self._run_trace(finding)
        traced = [f for f in confirmed if f.attack_path is not None]
        if not traced:
            self._goto(AssessmentState.REPORTING, "impact analysis failed for all findings")
            return self._finish()

        # ---- DIAGNOSIS (Diagnose)
        self._goto(AssessmentState.DIAGNOSIS)
        for finding in traced:
            self._run_diagnose(finding)
        diagnosed = [f for f in traced if f.plan is not None]
        if not diagnosed:
            self._goto(AssessmentState.REPORTING, "no remediation plan produced")
            return self._finish()

        # ---- AWAITING_APPROVAL gate (human only)
        self._goto(AssessmentState.AWAITING_APPROVAL)
        approved: list[FindingRecord] = []
        pending: list[str] = []
        for finding in diagnosed:
            try:
                approval = self.approve_remediation(finding) if self.approve_remediation else None
            except ApprovalPending as waiting:
                pending.append(waiting.finding_id)
                finding.notes.append("awaiting human remediation approval")
                self._audit(
                    "approval.requested",
                    "finding",
                    finding.finding_id,
                    approval_id=waiting.approval_id,
                )
                continue
            if approval is None:
                finding.notes.append("remediation not approved; finding stays diagnosed")
                self._audit("approval.absent", "finding", finding.finding_id)
                continue
            if approval.decision != "approved" or approval.subject_type != "remediation":
                finding.notes.append(f"remediation {approval.decision}")
                self._audit("approval.declined", "finding", finding.finding_id, approval_id=approval.id)
                continue
            if approval.subject_id != (finding.plan.id if finding.plan else ""):
                finding.notes.append("approval does not match this remediation plan; ignored")
                self._audit("approval.mismatch", "finding", finding.finding_id, approval_id=approval.id)
                continue
            if approval.decided_by.startswith("agent") or approval.decided_by == "system":
                finding.notes.append("approval was not made by a human; ignored")
                self._audit("approval.invalid_actor", "finding", finding.finding_id)
                continue
            finding.approval = approval
            approved.append(finding)
            self._audit(
                "approval.granted",
                "finding",
                finding.finding_id,
                actor="user",
                actor_id=approval.decided_by,
                approval_id=approval.id,
            )
        if pending and not approved:
            # Stop here, without a terminal transition: a host persists the
            # request and re-enters this orchestrator once a human decides.
            self.result.error_code = None
            return self.result
        if not approved:
            self._goto(AssessmentState.REPORTING, "no approved remediation")
            return self._finish()

        # ---- REMEDIATION (Patch <-> Verify sub-machine)
        self._goto(AssessmentState.REMEDIATION)
        for finding in approved:
            self._run_remediation(finding)

        # ---- HARDENING (Fortify) for verified findings
        self._goto(AssessmentState.HARDENING)
        for finding in approved:
            if finding.status == "verified":
                self._run_fortify(finding)

        self._goto(AssessmentState.REPORTING)
        return self._finish()

    def _finish(self) -> AssessmentResult:
        self._goto(AssessmentState.COMPLETED)
        self._audit(
            "assessment.completed",
            "assessment",
            self.config.assessment_id,
            findings=len(self.result.findings),
        )
        return self.result

    # ------------------------------------------------------------------ steps

    def _baseline_test_failures(self) -> list[str]:
        """Record which tests already fail on the unpatched snapshot (Verify needs this)."""
        ctx = self._context(AgentName.VERIFY, "baseline", services={})
        runner = TestRunner(
            driver=self.driver,
            workspace_provider=lambda _ctx: self.intel.snapshot.root,
            test_command_args=self.config.test_command_args,
        )
        result = runner.run(ctx, "project_suite", [])
        self._audit(
            "tests.baseline",
            "snapshot",
            self.intel.snapshot.snapshot_id,
            failing=result.get("failing_tests"),
            passed=result.get("passed"),
            sandbox_run_id=result.get("sandbox_run_id"),
        )
        self.result.usage.sandbox_seconds += float(result.get("duration_s") or 0)
        return list(result.get("failing_tests") or [])

    def _run_scout(self) -> list[Hypothesis]:
        data = scout_agent.ScoutInput(
            assessment_id=self.config.assessment_id,
            snapshot_id=self.intel.snapshot.snapshot_id,
            commit_sha=self.intel.snapshot.commit_sha,
            expectation_ids=[e.id for e in self.intel.expectations()],
            refuted_keys=self.history.refuted_keys(),
            max_hypotheses=self.config.max_hypotheses,
            available_check_categories=sorted(
                self.library.categories() & set(self.config.scope.allowed_check_categories)
            ),
        )
        ctx = self._context(AgentName.SCOUT, "recon", services=self._read_services())
        outcome = self._run_step(
            scout_agent.SPEC, ctx, scout_agent.build_prompt(data, self.intel), input_ref="scout:input"
        )
        if not outcome.ok or not isinstance(outcome.output, scout_agent.ScoutOutput):
            self._audit("recon.failed", "assessment", self.config.assessment_id, error=outcome.run.error_code)
            # A Scout that could not run is a failed assessment, not "no hypotheses":
            # reporting COMPLETED here would present an unexecuted review as clean.
            code = outcome.run.error_code or ErrorCode.LLM_UNAVAILABLE
            raise PlatformError(code, f"recon failed: {outcome.run.error_detail or code.value}"[:300])
        hypotheses = scout_agent.to_hypotheses(
            outcome.output, data, self.intel, max_items=self.config.max_hypotheses
        )
        ranked = scout_agent.rank(hypotheses, self.intel)
        for signal in outcome.output.suspicious_instructions:
            self._audit(
                "signal.suspicious_instruction",
                "snapshot",
                self.intel.snapshot.snapshot_id,
                detail=signal[:300],
            )
        for h in ranked:
            record = FindingRecord(finding_id=h.finding_id, hypothesis=h)
            self.result.findings.append(record)
            self.sink.on_finding(record)
            self._audit(
                "finding.hypothesis",
                "finding",
                h.finding_id,
                weakness_class=h.weakness_class,
                confidence=h.confidence.value,
            )
        return ranked

    def _finding_for(self, hypothesis_id: str) -> FindingRecord:
        return next(f for f in self.result.findings if f.hypothesis.id == hypothesis_id)

    def _run_validation(self, hypotheses: list[Hypothesis]) -> list[FindingRecord]:
        confirmed: list[FindingRecord] = []
        for index, hypothesis in enumerate(hypotheses[: self.config.max_hypotheses_to_validate]):
            finding = self._finding_for(hypothesis.id)
            data = probe_agent.input_from_hypothesis(
                hypothesis,
                assessment_id=self.config.assessment_id,
                scope_id=self.config.scope.id,
                target_id=self.config.target_id,
            )
            services = {
                **self._read_services(),
                "check_runner": CheckRunner(
                    driver=self.driver,
                    library=self.library,
                    workspace_provider=lambda _ctx: self.intel.snapshot.root,
                    recipe_provider=recipe_from_snapshot(self.intel),
                ),
            }
            ctx = self._context(AgentName.PROBE, f"validation:{index}", services=services)
            try:
                outcome = self._run_step(
                    probe_agent.SPEC,
                    ctx,
                    probe_agent.build_prompt(data, self.intel),
                    input_ref=f"probe:{hypothesis.id}",
                )
            except PlatformError as exc:
                if exc.code is ErrorCode.BUDGET_EXHAUSTED:
                    raise
                finding.status = "inconclusive"
                finding.notes.append(f"probe step failed: {exc.code.value}")
                continue
            check_runs = list(ctx.artifacts.get("check_runs") or [])
            for run in check_runs:
                self.result.usage.sandbox_seconds += float(run.get("duration_s") or 0)
            out = outcome.output if isinstance(outcome.output, probe_agent.ProbeOutput) else None
            if out is None:
                finding.status = "inconclusive"
                finding.notes.append(f"probe output invalid: {outcome.run.error_code}")
                continue
            validation = probe_agent.to_validation_result(out, data, outcome.record, check_runs)
            finding.validation = validation
            self.sink.on_record(finding, validation, "validation_result")
            finding.status = {
                ValidationOutcome.CONFIRMED: "validated",
                ValidationOutcome.REFUTED: "refuted",
                ValidationOutcome.INCONCLUSIVE: "inconclusive",
            }[validation.outcome]
            self._audit(
                "finding.validation",
                "finding",
                finding.finding_id,
                outcome=validation.outcome.value,
                sandbox_run_id=validation.sandbox_run_id,
                template=validation.check_template_id,
            )
            self.history.records.append(
                {
                    "key": hypothesis_key(
                        hypothesis.weakness_class,
                        hypothesis.cited_spans[0].path or "",
                        hypothesis.entry_point_id,
                    ),
                    "outcome": validation.outcome.value,
                    "finding_id": finding.finding_id,
                    "title": hypothesis.title,
                }
            )
            self._classify(finding)
            if validation.outcome is ValidationOutcome.CONFIRMED:
                confirmed.append(finding)
        return confirmed

    def _run_trace(self, finding: FindingRecord) -> None:
        assert finding.validation is not None
        paths = [s.path for s in finding.hypothesis.cited_spans if s.path]
        symbol = self._handler_symbol(finding)
        data = trace_agent.TraceInput(
            check_category=finding.hypothesis.suggested_check_category,
            assessment_id=self.config.assessment_id,
            finding_id=finding.finding_id,
            validation_result_id=finding.validation.id,
            sandbox_run_id=finding.validation.sandbox_run_id,
            hypothesis_title=finding.hypothesis.title,
            weakness_class=finding.hypothesis.weakness_class,
            confirmed_outcome=finding.validation.outcome.value,
            validation_observations=dict(finding.validation.observations),
            affected_paths=paths,
            affected_symbol=symbol,
            expectation_ids=list(finding.hypothesis.expectation_ids),
        )
        ctx = self._context(AgentName.TRACE, f"analysis:{finding.finding_id}", services=self._read_services())
        outcome = self._run_step(
            trace_agent.SPEC,
            ctx,
            trace_agent.build_prompt(data, self.intel),
            input_ref=f"trace:{finding.finding_id}",
        )
        if not isinstance(outcome.output, trace_agent.TraceOutput):
            finding.notes.append(f"trace failed: {outcome.run.error_code}")
            return
        path, severity = trace_agent.to_attack_path(
            outcome.output, data, self.intel, validation=finding.validation
        )
        finding.attack_path = path
        finding.severity = severity
        self.sink.on_record(finding, path, "attack_path")
        self._audit(
            "finding.severity",
            "finding",
            finding.finding_id,
            level=severity.level.value,
            factors=severity.factors.model_dump(mode="json"),
            verified_steps=sum(1 for s in path.steps if s.verified),
        )
        self._classify(finding)

    def _run_diagnose(self, finding: FindingRecord) -> None:
        assert finding.severity is not None and finding.attack_path is not None
        data = diagnose_agent.DiagnoseInput(
            assessment_id=self.config.assessment_id,
            finding_id=finding.finding_id,
            weakness_class=finding.hypothesis.weakness_class,
            hypothesis_title=finding.hypothesis.title,
            severity_level=finding.severity.level.value,
            impact_summary=finding.attack_path.impact_summary,
            validation_observations=dict(finding.validation.observations) if finding.validation else {},
            affected_symbol=self._handler_symbol(finding),
            affected_paths=[s.path for s in finding.hypothesis.cited_spans if s.path],
            violated_expectation_ids=list(finding.hypothesis.expectation_ids),
        )
        ctx = self._context(
            AgentName.DIAGNOSE, f"diagnosis:{finding.finding_id}", services=self._read_services()
        )
        outcome = self._run_step(
            diagnose_agent.SPEC,
            ctx,
            diagnose_agent.build_prompt(data, self.intel),
            input_ref=f"diagnose:{finding.finding_id}",
        )
        if not isinstance(outcome.output, diagnose_agent.DiagnoseOutput):
            finding.notes.append(f"diagnose failed: {outcome.run.error_code}")
            return
        try:
            root_cause, plan, related = diagnose_agent.to_plan(outcome.output, data, self.intel)
        except ValueError as exc:
            finding.notes.append(f"diagnose output unusable: {exc}")
            return
        finding.root_cause = root_cause
        finding.plan = plan
        finding.related_sites = related
        finding.status = "diagnosed"
        self.sink.on_record(finding, root_cause, "root_cause")
        self.sink.on_record(finding, plan, "remediation_plan")
        self.sink.on_status(finding, finding.status)
        self._audit(
            "finding.diagnosed",
            "finding",
            finding.finding_id,
            cause_class=root_cause.cause_class.value,
            plan_id=plan.id,
            files_expected=plan.files_expected,
        )

    def _run_remediation(self, finding: FindingRecord) -> None:
        assert finding.plan is not None and finding.approval is not None
        sub_state = RemediationState.PATCHING
        attempt = 1
        reasons: list[str] = []
        while True:
            if sub_state is RemediationState.PATCHING:
                candidate, _worktree = self._run_patch(finding, attempt, reasons)
                patch_failed = candidate is None
                sub_state = next_remediation_state(
                    sub_state, verdict=None, attempt=attempt, patch_failed=patch_failed
                )
                if sub_state is RemediationState.UNRESOLVED:
                    finding.status = "unresolved"
                    self._audit("remediation.unresolved", "finding", finding.finding_id, attempt=attempt)
                    return
                finding.status = "patch_proposed"
                continue
            if sub_state is RemediationState.VERIFYING:
                verification = self._run_verify(finding, attempt)
                verdict = verification.verdict if verification else "rejected"
                if verification:
                    finding.verifications.append(verification)
                    self.sink.on_verification(finding, verification)
                    reasons = list(verification.reasons)
                    self._audit(
                        "finding.verification",
                        "finding",
                        finding.finding_id,
                        verdict=verdict,
                        checks={c.name.value: c.passed for c in verification.checks},
                        verify_run_id=verification.verify_run_id,
                    )
                else:
                    reasons = ["verification step failed to execute"]
                sub_state = next_remediation_state(sub_state, verdict=verdict, attempt=attempt)
                if sub_state is RemediationState.ACCEPTED:
                    finding.status = "verified"
                    self.sink.on_status(finding, finding.status)
                    return
                if sub_state is RemediationState.UNRESOLVED:
                    finding.status = "patch_rejected"
                    self._audit("remediation.exhausted", "finding", finding.finding_id, attempts=attempt)
                    return
                attempt += 1
                continue
            raise PlatformError(ErrorCode.CONFLICT_STATE, f"bad remediation state {sub_state}")

    def _run_patch(
        self, finding: FindingRecord, attempt: int, reasons: list[str]
    ) -> tuple[PatchCandidate | None, PatchWorktree | None]:
        assert finding.plan is not None and finding.approval is not None
        worktree = PatchWorktree.create(
            self.intel,
            self.workdir / f"worktree-{finding.finding_id}-{attempt}",
            allowed_paths=list(finding.plan.files_expected),
        )
        data = patch_agent.input_from_plan(
            finding.plan,
            assessment_id=self.config.assessment_id,
            approval_id=finding.approval.id,
            attempt=attempt,
            cause_paths=[
                s.path for s in (finding.root_cause.cause_spans if finding.root_cause else []) if s.path
            ],
            prior_reasons=reasons,
        )
        services = {
            **self._read_services(),
            "worktree": worktree,
            "test_runner": TestRunner(
                driver=self.driver,
                workspace_provider=lambda _ctx, wt=worktree: wt,
                test_command_args=self.config.test_command_args,
            ),
        }
        ctx = self._context(
            AgentName.PATCH,
            f"remediation:{finding.finding_id}:patch",
            services=services,
            read_root=worktree.root,
        )
        outcome = self._run_step(
            patch_agent.SPEC,
            ctx,
            patch_agent.build_prompt(data, self.intel),
            input_ref=f"patch:{finding.plan.id}",
            attempt=attempt,
        )
        for run in ctx.artifacts.get("test_runs") or []:
            self.result.usage.sandbox_seconds += float(run.get("duration_s") or 0)
        if not isinstance(outcome.output, patch_agent.PatchOutput):
            finding.notes.append(f"patch attempt {attempt} failed: {outcome.run.error_code}")
            return None, worktree
        diff_uri = f"artifact://patch/{finding.finding_id}/{attempt}.diff"
        candidate, diff_text, notes = patch_agent.to_candidate(
            outcome.output, data, worktree, diff_uri=diff_uri
        )
        finding.notes.extend(notes)
        if candidate is None:
            return None, worktree
        (self.workdir / f"patch-{finding.finding_id}-{attempt}.diff").write_text(diff_text, encoding="utf-8")
        self._patch_artifacts[candidate.id] = {
            "diff": diff_text,
            "plan_files": list(finding.plan.files_expected),
            "protected_tests": self._protected_tests(),
        }
        finding.candidates.append(candidate)
        self.sink.on_patch(finding, candidate, diff_text)
        self._audit(
            "patch.candidate",
            "patch",
            candidate.id,
            actor="agent",
            actor_id="patch",
            files_changed=candidate.files_changed,
            tests_added=candidate.tests_added,
            diff_sha256=candidate.diff_sha256,
            attempt=attempt,
        )
        return candidate, worktree

    def _run_verify(self, finding: FindingRecord, attempt: int) -> VerificationResult | None:
        candidate = finding.candidates[-1]
        assert finding.plan is not None
        data = verify_agent.input_from_candidate(
            candidate,
            finding.plan,
            finding.validation,
            assessment_id=self.config.assessment_id,
            scope_id=self.config.scope.id,
            target_id=self.config.target_id,
            baseline_failing=self._baseline_failing,
        )
        applier = PatchApplier(intel=self.intel, artifacts=self._patch_artifacts, workdir=self.workdir)

        def verify_workspace(ctx: ToolContext) -> Any:
            # Verify runs tests/checks against the patched fresh checkout once it
            # has applied the diff; before that, against the pristine snapshot.
            return ctx.artifacts.get("verify_workspace") or self.intel.snapshot.root

        services = {
            **self._read_services(),
            "patch_applier": applier,
            "test_runner": TestRunner(
                driver=self.driver,
                workspace_provider=verify_workspace,
                test_command_args=self.config.test_command_args,
            ),
            "check_runner": CheckRunner(
                driver=self.driver,
                library=self.library,
                workspace_provider=verify_workspace,
                recipe_provider=recipe_from_snapshot(self.intel),
            ),
        }
        ctx = self._context(AgentName.VERIFY, f"remediation:{finding.finding_id}:verify", services=services)
        ctx.artifacts["tests_added"] = list(candidate.tests_added)
        outcome = self._run_step(
            verify_agent.SPEC,
            ctx,
            verify_agent.build_prompt(data, self.intel),
            input_ref=f"verify:{candidate.id}",
            attempt=attempt,
        )
        check_runs = list(ctx.artifacts.get("check_runs") or [])
        test_runs = list(ctx.artifacts.get("test_runs") or [])
        for run in check_runs + test_runs:
            self.result.usage.sandbox_seconds += float(run.get("duration_s") or 0)
        evidence = verify_agent.VerifyEvidence(
            apply_facts=dict(ctx.artifacts.get("verify_facts") or {}),
            recheck_runs=check_runs,
            test_runs=test_runs,
            baseline_failing=self._baseline_failing,
            tests_added=list(candidate.tests_added),
            protected_tests=self._protected_tests(),
            original_check_ref=data.original_check_template_ref,
            original_check_params=dict(data.original_check_parameters),
        )
        out = outcome.output if isinstance(outcome.output, verify_agent.VerifyOutput) else None
        sandbox_ids = [
            str(r.get("sandbox_run_id")) for r in check_runs + test_runs if r.get("sandbox_run_id")
        ]
        return verify_agent.to_result(
            out, data, evidence, sandbox_run_ids=sandbox_ids, verify_run_id=outcome.run.id
        )

    def _run_fortify(self, finding: FindingRecord) -> None:
        candidate = finding.candidates[-1] if finding.candidates else None
        verification = finding.verifications[-1] if finding.verifications else None
        if candidate is None or verification is None:
            return
        data = fortify_agent.FortifyInput(
            check_category=finding.hypothesis.suggested_check_category,
            assessment_id=self.config.assessment_id,
            finding_id=finding.finding_id,
            verification_result_id=verification.id,
            root_cause_summary=finding.root_cause.summary if finding.root_cause else finding.hypothesis.title,
            cause_class=finding.root_cause.cause_class.value if finding.root_cause else "unknown",
            cause_paths=[
                s.path for s in (finding.root_cause.cause_spans if finding.root_cause else []) if s.path
            ],
            related_sites=[r.symbol or "" for r in finding.related_sites][:10],
            tests_added=list(candidate.tests_added),
            affected_symbol=self._handler_symbol(finding),
        )
        ctx = self._context(
            AgentName.FORTIFY, f"hardening:{finding.finding_id}", services=self._read_services()
        )
        outcome = self._run_step(
            fortify_agent.SPEC,
            ctx,
            fortify_agent.build_prompt(data, self.intel),
            input_ref=f"fortify:{finding.finding_id}",
        )
        if not isinstance(outcome.output, fortify_agent.FortifyOutput):
            finding.notes.append(f"fortify failed: {outcome.run.error_code}")
            return
        tests, recommendations, drafts, hints = fortify_agent.to_records(outcome.output, data, self.intel)
        finding.regression_tests = tests
        finding.recommendations = recommendations
        finding.future_hypotheses = drafts
        finding.monitoring_hints = hints
        finding.status = "hardened"
        for recommendation in recommendations:
            self.sink.on_record(finding, recommendation, "hardening_recommendation")
        self._classify(finding)
        self.sink.on_status(finding, finding.status)
        self._audit(
            "finding.hardened",
            "finding",
            finding.finding_id,
            regression_tests=[t.test_path for t in tests],
            recommendations=len(recommendations),
            future_hypotheses=len(drafts),
        )

    # ------------------------------------------------------------------ helpers

    def _classify(self, finding: FindingRecord) -> None:
        try:
            finding.standards = standards_bridge.finding_standards(finding, now=self.now())
        except ValueError as exc:
            finding.notes.append(f"standards classification failed: {exc}"[:500])
            return
        self.sink.on_standards(finding)
        cvss = finding.standards.cvss
        self._audit(
            "finding.classified",
            "finding",
            finding.finding_id,
            cwe=finding.standards.cwe.id if finding.standards.cwe else None,
            attack=[m.id for m in finding.standards.attack],
            d3fend=[m.id for m in finding.standards.d3fend],
            cvss_vector=cvss.vector if cvss else None,
            cvss_complete=bool(cvss and cvss.complete),
        )

    def _handler_symbol(self, finding: FindingRecord) -> str | None:
        if finding.hypothesis.entry_point_id:
            for e in self.intel.entry_points():
                if e.id == finding.hypothesis.entry_point_id:
                    return e.handler_symbol
        path = finding.hypothesis.cited_spans[0].path
        line = (
            finding.hypothesis.cited_spans[0].span.start_line if finding.hypothesis.cited_spans[0].span else 1
        )
        for s in self.intel.symbols():
            if s.path == path and s.start_line <= line <= s.end_line and s.kind != "class":
                return s.qualified_name
        return None

    def _protected_tests(self) -> list[str]:
        """Tests encoding confirmed expectations (configured + expectation sources)."""
        protected = set(self.config.protected_tests)
        for expectation in self.intel.expectations():
            if expectation.status != "confirmed":
                continue
            for source in expectation.sources:
                if source.path and source.path.startswith("tests/"):
                    protected.add(source.path)
        return sorted(protected)
