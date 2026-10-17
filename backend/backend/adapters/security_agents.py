"""Host Alan's seven-agent runtime (``security_agents``) behind the backend contract.

``build_orchestrator()`` is the default ``ORCHESTRATOR_FACTORY``. The returned object
implements ``backend.host.Orchestrator`` and runs ``security_agents.Orchestrator``
inside the worker job, mirroring everything into ``AssessmentHost`` as it happens:

* every state transition -> ``host.transition`` (durable state + SSE + audit);
* every agent step -> ``host.start_agent_run`` / ``finish_agent_run`` with the role's
  model, provider mode (live/fake/replay), tool-call records, usage and transcript,
  and the usage is charged to the assessment budget (the backend budget gate applies);
* findings, hypotheses, validations, attack paths, root causes, plans, patches (diff
  stored as a hashed artifact) and Verify verdicts -> host records, translated from
  ``security_agents.contracts`` into ``shared`` models. ``verify_run_id`` is mapped
  to the backend run id, so the backend's Verify-independence gate is enforced too;
* remediation approval -> a real pending ``remediation`` Approval that a human
  decides via ``POST /approvals/{id}/decision``. The worker waits (lease heartbeats)
  up to ``APPROVAL_TIMEOUT_S``; decline or timeout continues to REPORTING (docs/08).

The runtime's approval callback is synchronous, so ``synchronous_approval = True``:
the backend does not re-run it on the approval's resume job (see ``pipeline``).

Translation is a typed local adapter until security_agents adopts ``shared``
(coordination message *-srihith-to-alan-orchestrator-integration, issue #17). It
subclasses two private methods (``_goto``, ``_run_step``) pending public hooks.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from backend.db import memberships, transaction
from backend.host import AssessmentHost, HostError
from backend.settings import Settings, get_settings
from shared.assessment import (
    TERMINAL_STATES,
    AgentName,
    AgentRunStatus,
    AssessmentState,
    ToolCallOutcome,
    ToolCallRecord,
)
from shared.base import utcnow
from shared.errors import ErrorBody, ErrorCode
from shared.evidence import ArtifactKind, EvidenceKind, EvidenceRef, SourceSpan
from shared.findings import (
    AttackPath,
    Finding,
    FindingKind,
    FindingStatus,
    HardeningRecommendation,
    Hypothesis,
    PatchCandidate,
    PathStep,
    RemediationPlan,
    RootCause,
    SeverityAssessment,
    SeverityFactors,
    SeverityLevel,
    StatusChange,
    ValidationOutcome,
    ValidationResult,
    VerificationCheck,
    VerificationCheckName,
    VerificationResult,
    VerificationVerdict,
)
from shared.ids import IdPrefix, new_id
from shared.scope import ApprovalStatus, ApprovalSubject, AuthorizedScope
from shared.tenancy import Usage

# Test hook (like backend.llm.TRANSPORT_OVERRIDE): (snapshot_root) -> security_agents LLMGateway.
GATEWAY_OVERRIDE: Callable[[Path], Any] | None = None


def _short(text: Any, n: int = 500) -> str:
    return str(text or "")[:n]


_CONFIDENCE = {"low": 0.3, "medium": 0.6, "high": 0.9}


def _conf(value: Any) -> float:
    """security_agents uses an enum (low/medium/high); shared uses a 0..1 float."""
    raw = getattr(value, "value", value)
    if isinstance(raw, int | float):
        return max(0.0, min(1.0, float(raw)))
    return _CONFIDENCE.get(str(raw).lower(), 0.5)


def _code(value: Any) -> ErrorCode:
    try:
        return ErrorCode(getattr(value, "value", value))
    except ValueError:
        return ErrorCode.INTERNAL


@dataclass(frozen=True)
class RepoBinding:
    repo_id: str
    local_path: Path
    subdir: str


def load_bindings(settings: Settings) -> dict[str, RepoBinding]:
    if not settings.repository_bindings_file or not settings.repository_bindings_file.exists():
        return {}
    out = {}
    for raw in json.loads(settings.repository_bindings_file.read_text()):
        b = RepoBinding(
            raw["repo_id"], Path(raw["local_path"]).expanduser().resolve(), raw.get("subdir", ".")
        )
        out[b.repo_id] = b
    return out


class _Translator:
    """security_agents.contracts -> shared, with artifacts stored through the host."""

    def __init__(self, host: AssessmentHost, commit_sha: str) -> None:
        self.host = host
        self.sha = commit_sha
        self.run_ids: dict[str, str] = {}  # security_agents run id -> backend run id

    def evidence(self, e: Any, *, payload: Any = None) -> EvidenceRef:
        prov = f"security_agents:{e.provenance}"
        if e.path and e.span:
            return EvidenceRef(
                kind=EvidenceKind.source_span,
                path=e.path,
                commit_sha=e.sha or self.sha,
                span=SourceSpan(start_line=e.span.start_line, end_line=e.span.end_line),
                symbol=_short(e.symbol) or None,
                provenance=prov,
            )
        kind = {"check_run": EvidenceKind.sandbox_run, "test_run": EvidenceKind.test_run}.get(
            e.provenance, EvidenceKind.tool_output
        )
        ref = self.host.store_json(
            {"reference": e.model_dump(mode="json"), "detail": payload}, ArtifactKind.tool_output
        )
        return EvidenceRef(
            kind=kind,
            artifact_id=ref.id,
            sha256=ref.sha256,
            provenance=prov,
            path=e.path or None,
            note=_short(e.artifact_id, 200) or None,
        )

    def evidences(
        self, items: list[Any], *, payload: Any = None, fallback: Any = None
    ) -> list[EvidenceRef]:
        out = [self.evidence(e, payload=payload) for e in items]
        if not out and fallback is not None:
            ref = self.host.store_json(fallback, ArtifactKind.tool_output)
            out = [
                EvidenceRef(
                    kind=EvidenceKind.tool_output,
                    artifact_id=ref.id,
                    sha256=ref.sha256,
                    provenance="security_agents:reported",
                )
            ]
        return out

    def run(self, sa_run_id: str | None) -> str | None:
        return self.run_ids.get(sa_run_id or "")


class HostedSecurityOrchestrator:
    synchronous_approval = True

    def __init__(self, settings: Settings | None = None) -> None:
        import security_agents  # noqa: F401  (fail fast: reported as unavailable by load_factory)

        self._settings = settings

    @property
    def settings(self) -> Settings:
        # Read at use time: the worker keeps this object for the life of the process.
        return self._settings or get_settings()

    # ------------------------------------------------------------- wiring
    def _gateway(self, snapshot_root: Path) -> Any:
        if GATEWAY_OVERRIDE is not None:
            return GATEWAY_OVERRIDE(snapshot_root)
        from security_agents.llm import ProviderGateway
        from security_agents.llm.providers import AnthropicProvider

        key = (
            self.settings.anthropic_api_key.get_secret_value()
            if self.settings.anthropic_api_key
            else ""
        )
        if not key:
            raise HostError(
                ErrorCode.LLM_UNAVAILABLE,
                "ANTHROPIC_API_KEY is not configured; live agents unavailable",
            )
        import anthropic

        client = anthropic.Anthropic(
            api_key=key, max_retries=0, timeout=self.settings.llm_request_timeout_s
        )
        overrides = None
        if self.settings.agent_model_overrides:
            from security_agents.llm.gateway import parse_overrides

            overrides = parse_overrides(self.settings.agent_model_overrides)
        return ProviderGateway(
            AnthropicProvider(client),
            default_model=self.settings.anthropic_model,
            overrides=overrides or {},
        )

    def _driver(self) -> Any:
        from security_agents.sandbox.driver import DockerSandboxDriver, LocalProcessDriver

        if self.settings.security_sandbox == "local-dev":
            if not self.settings.is_dev:
                raise HostError(
                    ErrorCode.SANDBOX_POLICY_VIOLATION,
                    "local-dev sandbox is only allowed in development/test",
                )
            return LocalProcessDriver(allow=True)
        return DockerSandboxDriver()

    def _scope(self, host: AssessmentHost, scope: AuthorizedScope, target_id: str) -> Any:
        from security_agents.contracts import AuthorizedScope as SAScope
        from security_agents.contracts import ScopeStatus as SAStatus
        from security_agents.contracts import ScopeTarget as SATarget

        return SAScope(
            id=scope.id,
            project_id=scope.project_id,
            name=scope.name,
            targets=[
                SATarget(
                    target_id=target_id if t.repo_id == host.repo_id else f"tgt_{t.repo_id}",
                    repo_id=t.repo_id,
                    build_recipe_ref=t.build_recipe_ref,
                    exposed_ports=t.exposed_ports,
                )
                for t in scope.targets
            ],
            allowed_check_categories=scope.allowed_check_categories,
            status=SAStatus(scope.status.value),
            requested_by=scope.requested_by,
            approved_by=scope.approved_by,
            approved_at=scope.approved_at,
            expires_at=scope.expires_at,
            notes=scope.notes or "",
        )

    # ---------------------------------------------------------------- run
    def run(self, host: AssessmentHost) -> None:
        from security_agents.checks.library import default_library
        from security_agents.contracts import Budget as SABudget
        from security_agents.intel import LocalIntel
        from security_agents.workflow import Orchestrator, OrchestratorConfig

        a = host.assessment
        binding = load_bindings(self.settings).get(host.repo_id)
        if binding is None:
            raise HostError(
                ErrorCode.SUBSYSTEM_UNAVAILABLE,
                f"no trusted local checkout bound for {host.repo_id} (REPOSITORY_BINDINGS_FILE)",
            )
        scope = host.require_active_scope()
        work = (
            Path(self.settings.security_workdir or tempfile.gettempdir())
            / "hackatl-security"
            / a.id
        )
        try:
            snapshot = _pinned_snapshot(
                binding,
                a.commit_sha,
                work,
                snapshot_id=a.snapshot_id or new_id(IdPrefix.snp),
                repo_id=host.repo_id,
            )
        except Exception as exc:
            raise HostError(
                ErrorCode.SNAPSHOT_NOT_READY, f"cannot check out {a.commit_sha[:12]}: {exc}"
            ) from exc
        with transaction() as conn:
            members = conn.execute(
                sa.select(sa.func.count())
                .select_from(memberships)
                .where(memberships.c.org_id == host.org_id)
            ).scalar_one()
        target_id = f"tgt_{host.repo_id}"
        config = OrchestratorConfig(
            assessment_id=a.id,
            project_id=a.project_id,
            org_id=host.org_id,
            scope=self._scope(host, scope, target_id),
            target_id=target_id,
            requested_by=a.created_by or scope.requested_by,
            budget=SABudget(
                max_tokens=a.budget.max_tokens,
                max_usd=a.budget.max_usd,
                max_wall_clock_s=float(a.budget.max_wall_clock_s),
            ),
            org_member_count=members,
        )
        gateway = self._gateway(snapshot.root)
        tr = _Translator(host, a.commit_sha)
        hosted = self

        class Mirrored(Orchestrator):  # type: ignore[misc, valid-type]
            def _goto(self, dst: Any, note: str = "") -> None:
                super()._goto(dst, note)
                target = AssessmentState(dst.value.upper())
                if target not in TERMINAL_STATES or target is AssessmentState.COMPLETED:
                    hosted._sync_findings(host, tr, self.result.findings, orch=self)
                    host.transition(target, f"{dst.value}{': ' + note if note else ''}"[:500])

            def _run_step(
                self, spec: Any, ctx: Any, prompt: str, *, input_ref: str, attempt: int = 1
            ) -> Any:
                key = f"{ctx.step_key}#{attempt}"
                if key in self._completed_steps:
                    return self._completed_steps[key]
                agent = AgentName(spec.name.value)
                run_id = host.start_agent_run(
                    agent,
                    ctx.step_key[:500],
                    attempt=attempt,
                    provider_mode=gateway.mode,
                    model_id=gateway.model_for(spec.name),
                    prompt_version=f"{agent.value}@{spec.version}",
                    input_payload={
                        "input_ref": input_ref,
                        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    },
                )
                try:
                    outcome = super()._run_step(
                        spec, ctx, prompt, input_ref=input_ref, attempt=attempt
                    )
                except Exception as exc:
                    host.finish_agent_run(
                        run_id,
                        AgentRunStatus.failed,
                        error=ErrorBody(
                            code=_code(getattr(exc, "code", None)), message=_short(exc)
                        ),
                    )
                    raise
                tr.run_ids[outcome.run.id] = run_id
                hosted._finish_run(host, run_id, outcome)
                return outcome

        orch = Mirrored(
            config,
            intel=LocalIntel(snapshot),
            gateway=gateway,
            driver=self._driver(),
            library=default_library(),
            workdir=work / "run",
            approve_remediation=lambda finding: self._await_approval(host, tr, finding),
            kill_switch=lambda: self._scope_revoked(host),
            cancelled=lambda: self._cancel_requested(host),
        )
        self._orch = orch
        result = orch.run()
        self._sync_findings(host, tr, result.findings, final=True, orch=orch)
        if result.state.value != "completed":
            code = _code(result.error_code) if result.error_code else ErrorCode.INTERNAL
            state = {
                ErrorCode.BUDGET_EXHAUSTED: AssessmentState.BUDGET_EXHAUSTED,
                ErrorCode.CANCELLED: AssessmentState.CANCELLED,
            }.get(code, AssessmentState.FAILED)
            if host.assessment.state not in TERMINAL_STATES:
                host.terminate(state, code, _short(result.error_detail or result.state.value))

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _scope_revoked(host: AssessmentHost) -> bool:
        try:
            host.require_active_scope()
            return False
        except HostError:
            return True

    @staticmethod
    def _cancel_requested(host: AssessmentHost) -> bool:
        try:
            host.check_cancelled()
            return False
        except Exception:
            return True

    @staticmethod
    def _finish_run(host: AssessmentHost, run_id: str, outcome: Any) -> None:
        run, record = outcome.run, outcome.record
        calls = []
        for i, t in enumerate(record.tool_invocations):
            digest = hashlib.sha256(
                json.dumps(t.args, sort_keys=True, default=str).encode()
            ).hexdigest()
            outcome_kind = (
                ToolCallOutcome.ok
                if t.ok
                else ToolCallOutcome.denied
                if t.error_code in ("TOOL_NOT_ALLOWED", "SCOPE_DENIED")
                else ToolCallOutcome.error
            )
            calls.append(
                ToolCallRecord(
                    turn=i + 1,
                    tool_name=_short(t.name),
                    input_sha256=digest,
                    outcome=outcome_kind,
                    error_code=_code(t.error_code) if t.error_code else None,
                    duration_ms=0,
                )
            )
        usage = Usage(
            input_tokens=run.usage.input_tokens,
            output_tokens=run.usage.output_tokens,
            usd=round(run.usage.usd, 6),
            sandbox_seconds=run.usage.sandbox_seconds,
            llm_calls=run.llm_turns,
            tool_calls=run.tool_calls,
        )
        status = AgentRunStatus.succeeded if run.status == "succeeded" else AgentRunStatus.failed
        error = (
            ErrorBody(
                code=_code(run.error_code), message=_short(run.error_detail or "agent step failed")
            )
            if status is AgentRunStatus.failed
            else None
        )
        host.finish_agent_run(
            run_id,
            status,
            usage=usage,
            tool_calls=calls,
            output=outcome.output.model_dump(mode="json") if outcome.output is not None else None,
            transcript={
                "turns": record.turns,
                "spec_version": record.spec_version,
                "model": record.model,
                "provider_mode": record.provider_mode,
                "security_agents_run_id": run.id,
            },
            error=error,
        )
        host.charge(usage)  # backend budget gate (raises BUDGET_EXHAUSTED when exceeded)

    def _await_approval(self, host: AssessmentHost, tr: _Translator, finding: Any) -> Any:
        from security_agents.contracts import Approval as SAApproval

        if finding.plan is None:
            return None
        self._sync_findings(host, tr, [finding], orch=getattr(self, "_orch", None))
        ap = host.request_approval(
            ApprovalSubject.remediation,
            finding.plan.id,
            _short(f"{finding.finding_id}: {finding.plan.strategy}"),
        )
        deadline = time.monotonic() + self.settings.approval_timeout_s
        while time.monotonic() < deadline:
            host.check_cancelled()
            current = next((x for x in host.approvals() if x.id == ap.id), None)
            if current is not None and current.status is not ApprovalStatus.pending:
                return SAApproval(
                    id=current.id,
                    project_id=current.project_id,
                    subject_type="remediation",
                    subject_id=finding.plan.id,
                    decision=current.status.value,
                    decided_by=current.decided_by or "system",
                    decided_at=current.decided_at or utcnow(),
                    reason=current.reason,
                )
            time.sleep(self.settings.approval_poll_s)
        host.progress(
            f"approval {ap.id} timed out after {self.settings.approval_timeout_s}s; continuing without remediation"
        )
        return None

    # ------------------------------------------------------ finding sync
    def _sync_findings(
        self,
        host: AssessmentHost,
        tr: _Translator,
        records: list[Any],
        *,
        final: bool = False,
        orch: Any = None,
    ) -> None:
        for rec in records:
            self._sync_one(host, tr, rec, orch)

    _synced: set[str]

    def _sync_one(self, host: AssessmentHost, tr: _Translator, rec: Any, orch: Any) -> None:
        if not hasattr(self, "_synced"):
            self._synced = set()
        h = rec.hypothesis
        try:
            status = FindingStatus(rec.status)
        except ValueError:
            status = FindingStatus.inconclusive
        evidence = tr.evidences(h.cited_spans)
        if rec.validation is not None:
            evidence += tr.evidences(
                rec.validation.evidence,
                payload=rec.validation.observations,
                fallback={"validation": rec.validation.model_dump(mode="json")},
            )
        severity = None
        if rec.severity is not None:
            f = rec.severity.factors
            severity = SeverityAssessment(
                level=SeverityLevel(rec.severity.level.value),
                rationale=_short(rec.severity.rationale),
                factors=SeverityFactors(
                    reachability=f.reachability,
                    privileges_required=f.privileges_required,
                    data_sensitivity=f.data_sensitivity,
                    verified_path=f.verified_path,
                ),
            )
        subjects = sorted({s.symbol for s in h.cited_spans if s.symbol})
        route = self._route_for(orch, h)
        if route:
            subjects.append(route)
        now = utcnow()
        existing = next((x for x in host.findings() if x.id == rec.finding_id), None)
        history = list(existing.history) if existing else []
        if existing is None or existing.status is not status:
            history.append(
                StatusChange(
                    from_status=existing.status if existing else None,
                    to_status=status,
                    at=now,
                    actor="agent:security_agents",
                )
            )
        host.record_finding(
            Finding(
                id=rec.finding_id,
                assessment_id=host.assessment_id,
                snapshot_id=None,
                commit_sha=tr.sha,
                kind=FindingKind.security,
                title=_short(h.title),
                status=status,
                severity=severity,
                subject_refs=[_short(s) for s in subjects][:20],
                expectation_ids=[e for e in h.expectation_ids if _valid("exp", e)],
                evidence=evidence,
                confidence=_conf(h.confidence),
                produced_by_run_id=None,
                history=history,
                created_at=existing.created_at if existing else now,
                updated_at=now,
            ),
            actor="agent:security_agents",
        )
        self._sync_records(host, tr, rec)
        if orch is not None:
            self._sync_patches(host, tr, rec, orch)

    @staticmethod
    def _route_for(orch: Any, h: Any) -> str | None:
        if orch is None or not getattr(h, "entry_point_id", None):
            return None
        for ep in orch.intel.entry_points():
            if ep.id == h.entry_point_id and ep.method and ep.path_template:
                return f"{ep.method.upper()} {ep.path_template}"
        return None

    def _once(self, key: str) -> bool:
        if key in self._synced:
            return False
        self._synced.add(key)
        return True

    def _sync_records(self, host: AssessmentHost, tr: _Translator, rec: Any) -> None:
        fid, h = rec.finding_id, rec.hypothesis
        if self._once(h.id):
            host.record(
                fid,
                Hypothesis(
                    id=h.id,
                    finding_id=fid,
                    weakness_class=h.weakness_class,
                    rationale=_short(h.rationale),
                    cited_spans=tr.evidences(h.cited_spans),
                    expectation_ids=[e for e in h.expectation_ids if _valid("exp", e)],
                    confidence=_conf(h.confidence),
                    suggested_check_category=_short(h.suggested_check_category),
                ),
            )
        v = rec.validation
        if v is not None and self._once(v.id):
            host.record(
                fid,
                ValidationResult(
                    id=v.id,
                    hypothesis_id=h.id,
                    outcome=ValidationOutcome(v.outcome.value),
                    check_template_id=_short(v.check_template_id or "none"),
                    check_template_version=_short(v.check_template_version or "none"),
                    sandbox_run_id=_short(v.sandbox_run_id or "none"),
                    evidence=tr.evidences(
                        v.evidence,
                        payload=v.observations,
                        fallback={"validation": v.model_dump(mode="json")},
                    ),
                ),
            )
        p = rec.attack_path
        if p is not None and self._once(p.id):
            host.record(
                fid,
                AttackPath(
                    id=p.id,
                    finding_id=fid,
                    impact_summary=_short(p.impact_summary),
                    preconditions=[_short(x) for x in p.preconditions],
                    steps=[
                        PathStep(
                            order=s.order,
                            description=_short(s.description),
                            symbol_ref=s.symbol_ref,
                            verified=s.verified,
                            evidence=tr.evidences(s.evidence),
                        )
                        for s in p.steps
                    ],
                ),
            )
        rc = rec.root_cause
        if rc is not None and self._once(rc.id):
            host.record(
                fid,
                RootCause(
                    id=rc.id,
                    finding_id=fid,
                    summary=_short(rc.summary),
                    violated_expectation_ids=[
                        e for e in rc.violated_expectation_ids if _valid("exp", e)
                    ],
                    cause_spans=tr.evidences(rc.cause_spans),
                    cause_class=rc.cause_class.value,
                ),
            )
        plan = rec.plan
        if plan is not None and self._once(plan.id):
            host.record(
                fid,
                RemediationPlan(
                    id=plan.id,
                    finding_id=fid,
                    strategy=_short(plan.strategy),
                    constraints=[_short(c) for c in plan.constraints],
                    files_expected=list(plan.files_expected),
                    test_plan=_short(plan.test_plan.model_dump_json()),
                ),
            )
        for hr in rec.recommendations:
            if self._once(hr.id):
                host.record(
                    fid,
                    HardeningRecommendation(
                        id=hr.id,
                        finding_id=fid,
                        category=hr.category,
                        recommendation=_short(hr.recommendation),
                        effort=hr.effort,
                    ),
                )

    def _sync_patches(self, host: AssessmentHost, tr: _Translator, rec: Any, orch: Any) -> None:
        patch_runs = [
            run
            for run in orch.result.runs
            if run.agent.value == "patch" and run.step_key.endswith(f"{rec.finding_id}:patch")
        ]
        for c in rec.candidates:
            if not self._once(c.id):
                continue
            diff = (orch._patch_artifacts.get(c.id) or {}).get("diff", "")
            ref = host.store_text(diff, ArtifactKind.diff, media_type="text/x-diff")
            run = next((r for r in patch_runs if r.attempt == c.attempt), None)
            produced = tr.run(run.id if run else None)
            if produced is None or not c.files_changed:
                continue
            host.record_patch(
                PatchCandidate(
                    id=c.id,
                    finding_id=rec.finding_id,
                    attempt=c.attempt,
                    diff_artifact_id=ref.id,
                    diff_sha256=ref.sha256,
                    base_commit_sha=tr.sha,
                    worktree_ref=_short(c.worktree_ref),
                    files_changed=list(c.files_changed),
                    tests_added=[_short(t) for t in c.tests_added],
                    produced_by_run_id=produced,
                    rationale=_short(rec.plan.strategy if rec.plan else "security remediation"),
                    created_at=utcnow(),
                )
            )
        for v in rec.verifications:
            produced = tr.run(v.verify_run_id)
            if produced is None or not self._once(v.id):
                continue
            checks = [
                VerificationCheck(
                    name=VerificationCheckName(c.name.value),
                    passed=c.passed,
                    evidence=tr.evidences(
                        c.evidence,
                        payload={"detail": c.detail},
                        fallback={
                            "check": c.model_dump(mode="json"),
                            "sandbox_run_ids": v.sandbox_run_ids,
                        },
                    ),
                )
                for c in v.checks
            ]
            if not checks:
                continue
            host.record_verification(
                VerificationResult(
                    id=v.id,
                    patch_id=v.patch_id,
                    verdict=VerificationVerdict(v.verdict),
                    checks=checks,
                    sandbox_run_ids=[_short(s, 200) for s in v.sandbox_run_ids] or ["none"],
                    reasons=[_short(r) for r in v.reasons],
                    produced_by_run_id=produced,
                    created_at=utcnow(),
                )
            )


def _valid(prefix: str, value: str) -> bool:
    import re

    return bool(re.match(rf"^{prefix}_[0-9A-Za-z_\-]{{8,64}}$", value))


def _pinned_snapshot(
    binding: RepoBinding, sha: str, work: Path, *, snapshot_id: str, repo_id: str
) -> Any:
    """Read-only checkout of ``binding.subdir`` at exactly ``sha`` (git archive).

    If the directory holds a ``build_recipe.json`` with ``target_dir`` (payments-lite
    layout on main), the snapshot is rooted at that directory with the recipe copied in,
    as security_agents expects; provenance stays ``pinned_by="git"`` at the real SHA.
    """
    import shutil

    from security_agents.sandbox.workspace import SnapshotHandle, copy_tree

    raw = SnapshotHandle.from_git(
        binding.local_path,
        sha,
        binding.subdir,
        work / "checkout",
        snapshot_id=snapshot_id,
        repo_id=repo_id,
    )
    recipe = raw.root / "build_recipe.json"
    target_dir = json.loads(recipe.read_text()).get("target_dir") if recipe.is_file() else None
    if not target_dir:
        return raw
    if target_dir.startswith("/") or ".." in Path(target_dir).parts:
        raise ValueError("build_recipe.json target_dir must be a relative path inside the checkout")
    root = work / "snapshot"
    copy_tree(raw.root / target_dir, root)
    shutil.copy2(recipe, root / "build_recipe.json")
    for path in root.rglob("*"):  # same policy as security_agents: files read-only
        if path.is_file():
            path.chmod(0o444)
    return SnapshotHandle(
        snapshot_id=snapshot_id,
        repo_id=repo_id,
        commit_sha=raw.commit_sha,
        root=root,
        pinned_by="git",
    )


def build_orchestrator() -> HostedSecurityOrchestrator:
    return HostedSecurityOrchestrator()
