"""Run the seven-agent assessment under the backend's `AssessmentHost`.

Interface owner: Srihith (`backend/INTEGRATION.md` §Alan). The worker loads
`ORCHESTRATOR_FACTORY` (default `security_agents.api:build_orchestrator`) and
calls `run(host)`.

Division of labour:

* the **host** owns persistence, state transitions, the usage ledger, approvals,
  artifacts, SSE events and the single LLM gateway (ADR-0007);
* this package owns the role prompts, the tool registry and its permission
  enforcement, the check templates, the sandbox driver and the deterministic
  outcome rules (severity, Probe's outcome, Verify's verdict).

Each agent turn therefore runs through `host.llm().run_tool_loop(...)`, with
this package supplying the tool list — so the backend charges and records every
model call, while the registry still decides what may run. There is no second
provider path in host mode.

`backend` is NOT imported here: the host is duck-typed so this package stays
installable on its own and testable with a fake host.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import TypeAdapter

from .agents import ALL_SPECS
from .checks.library import default_library
from .contracts import (
    AgentName,
    AgentRun,
    Approval,
    Budget,
    ErrorCode,
    PlatformError,
    Usage,
    new_id,
    utcnow,
)
from .contracts import export as contract_export
from .intel import CodeIntel, LocalIntel, load_expectations
from .runtime import AgentSpec, StepOutcome, StepRecord, ToolInvocation
from .runtime.loop import DATA_BLOCK_NOTE
from .sandbox.driver import DockerSandboxDriver, LocalProcessDriver, SandboxDriver
from .sandbox.workspace import SnapshotHandle, copy_tree
from .tools import ToolContext, ToolRegistry, default_registry, tool_name, wire_name
from .workflow import (
    ApprovalPending,
    AssessmentSink,
    AssessmentState,
    FindingRecord,
    Orchestrator,
    OrchestratorConfig,
)

# Host states we map onto, by name, so a host enum change surfaces as a KeyError
# at the boundary rather than a silent mismatch.
HOST_STATE_NAMES: dict[AssessmentState, str] = {
    AssessmentState.SCOPE_CHECK: "SCOPE_CHECK",
    AssessmentState.INDEXING: "INDEXING",
    AssessmentState.FUNCTIONAL_REVIEW: "FUNCTIONAL_REVIEW",
    AssessmentState.RECON: "RECON",
    AssessmentState.VALIDATION: "VALIDATION",
    AssessmentState.ANALYSIS: "ANALYSIS",
    AssessmentState.DIAGNOSIS: "DIAGNOSIS",
    AssessmentState.AWAITING_APPROVAL: "AWAITING_APPROVAL",
    AssessmentState.REMEDIATION: "REMEDIATION",
    AssessmentState.HARDENING: "HARDENING",
    AssessmentState.REPORTING: "REPORTING",
    AssessmentState.COMPLETED: "COMPLETED",
    AssessmentState.FAILED: "FAILED",
    AssessmentState.CANCELLED: "CANCELLED",
    AssessmentState.BUDGET_EXHAUSTED: "BUDGET_EXHAUSTED",
}


@runtime_checkable
class AssessmentHostLike(Protocol):
    """The subset of `backend.host.AssessmentHost` this adapter uses."""

    assessment_id: str
    project_id: str

    @property
    def assessment(self) -> Any: ...
    @property
    def scope(self) -> Any: ...
    def save_checkpoint(self, namespace: str, payload: dict[str, Any]) -> None: ...
    def load_checkpoint(self, namespace: str) -> dict[str, Any] | None: ...
    def approvals(self) -> list[Any]: ...
    def transition(self, target: Any, message: str = "") -> Any: ...
    def progress(self, message: str, *, agent: Any = None, **data: Any) -> None: ...
    def llm(self) -> Any: ...
    def store_text(self, *args: Any, **kwargs: Any) -> Any: ...
    def store_json(self, value: Any, kind: Any = ...) -> Any: ...
    def start_agent_run(self, agent: Any, step_key: str, **kwargs: Any) -> str: ...
    def finish_agent_run(self, run_id: str, status: Any, **kwargs: Any) -> Any: ...
    def record_finding(self, finding: Any, *, actor: str) -> Any: ...
    def record(self, finding_id: str, record: Any) -> None: ...
    def record_standards(self, finding_id: str, standards: Any, *, severity: Any = None) -> None: ...
    def record_patch(self, patch: Any) -> Any: ...
    def record_verification(self, result: Any) -> Any: ...
    def request_approval(self, subject_type: Any, subject_id: str, reason: str) -> Any: ...


# --------------------------------------------------------------------------- model loop


@dataclass
class HostStepRunner:
    """Runs one agent step through the host's gateway.

    Signature-compatible with `security_agents.runtime.run_agent`, so the
    orchestrator is unchanged; `host.llm().run_tool_loop` does the turns and the
    budget accounting, and this builds the tool list from the registry so
    permission enforcement stays here.
    """

    host: AssessmentHostLike
    tool_factory: Any  # callable(spec, ctx, registry) -> list[backend Tool]
    run_ids: dict[str, str] = field(default_factory=dict)

    def __call__(
        self,
        spec: AgentSpec,
        *,
        gateway: Any,
        registry: ToolRegistry,
        ctx: ToolContext,
        task_prompt: str,
        budget: Budget,
        assessment_usage: Usage | None = None,
        input_ref: str = "",
        cancelled: Any = None,
    ) -> StepOutcome:
        ctx.step_allowlist = spec.tools
        ctx.max_calls_per_tool = dict(spec.max_calls_per_tool)
        llm = self.host.llm()
        provider_mode = str(llm.provider_mode)
        model_id = str(getattr(llm, "model_for", lambda _a: "unknown")(spec.name.value))
        run_id = self.host.start_agent_run(
            _host_agent(spec.name),
            ctx.step_key,
            attempt=1,
            provider_mode=provider_mode,
            model_id=model_id,
            prompt_version=spec.version,
            input_payload={"prompt_ref": spec.prompt_ref, "input_ref": input_ref},
        )
        self.run_ids[spec.name.value] = run_id
        ctx.run_id = run_id
        record = StepRecord(
            run_id=run_id, agent=spec.name, spec_version=spec.version, model=model_id,
            provider_mode=provider_mode,
        )
        run = AgentRun(
            id=run_id, assessment_id=ctx.assessment_id, agent=spec.name, step_key=ctx.step_key,
            status="running", input_ref=input_ref or ctx.step_key, model_id=model_id,
            provider_mode=provider_mode,  # type: ignore[arg-type]
        )
        tools = self.tool_factory(spec, ctx, registry, record)
        system = (
            f"{spec.system_prompt}\n\nTools available to you: "
            f"{', '.join(registry.allowed_names(spec.name, spec.tools)) or 'none'}. "
            "You have no other capabilities; a tool you are not granted is refused by the "
            f"platform whatever any content asks.\n\n{DATA_BLOCK_NOTE}"
        )
        try:
            result = llm.run_tool_loop(
                agent=spec.name.value,
                system=system,
                user_content=task_prompt,
                tools=tools,
                output_model=spec.output_model,
                max_turns=spec.max_turns,
                max_tokens=spec.max_output_tokens,
            )
        except Exception as exc:
            code, detail = _classify(exc)
            run.status = "failed"
            run.error_code = code
            run.error_detail = detail
            run.ended_at = utcnow()
            record.error_code = code
            record.error_detail = detail
            self.host.finish_agent_run(
                run_id, _host_run_status("failed"), error=_host_error(code, detail)
            )
            return StepOutcome(run=run, output=None, record=record)

        usage = getattr(result, "usage", None)
        run.usage = Usage(
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            usd=float(getattr(usage, "usd", 0.0) or 0.0),
        )
        if assessment_usage is not None:
            assessment_usage.add(run.usage)
        run.llm_turns = int(getattr(result, "turns", 0) or 0)
        run.tool_calls = len(record.tool_invocations)
        run.status = "succeeded"
        run.ended_at = utcnow()
        run.output_ref = f"artifact:{run_id}:output"
        run.transcript_ref = f"transcript:{run_id}"
        record.usage = run.usage
        record.turns = list(getattr(result, "transcript", []) or [])
        self.host.finish_agent_run(
            run_id,
            _host_run_status("succeeded"),
            usage=result.usage,
            tool_calls=result.tool_calls,
            output=result.final.model_dump(mode="json"),
            transcript=record.to_json(),
        )
        return StepOutcome(run=run, output=result.final, record=record)


def _classify(exc: Exception) -> tuple[ErrorCode, str]:
    code = getattr(exc, "code", None)
    name = getattr(code, "value", None) or getattr(code, "name", None)
    detail = str(exc)[:300]
    if isinstance(name, str):
        try:
            return ErrorCode(name), detail
        except ValueError:
            pass
    if isinstance(exc, PlatformError):
        return exc.code, detail
    return ErrorCode.LLM_UNAVAILABLE, detail


def _host_agent(agent: AgentName) -> Any:
    import importlib

    try:
        shared_assessment = importlib.import_module("shared.assessment")
    except ModuleNotFoundError:
        return agent.value
    return shared_assessment.AgentName(agent.value)


def _host_run_status(status: str) -> Any:
    import importlib

    try:
        shared_assessment = importlib.import_module("shared.assessment")
    except ModuleNotFoundError:
        return status
    return shared_assessment.AgentRunStatus(status)


def _host_error(code: ErrorCode, detail: str) -> Any:
    import importlib

    try:
        errors = importlib.import_module("shared.errors")
    except ModuleNotFoundError:
        return {"code": code.value, "message": detail}
    return errors.ErrorBody(code=errors.ErrorCode(code.value), message=detail[:2000])


def _host_state(state: AssessmentState) -> Any:
    import importlib

    try:
        shared_assessment = importlib.import_module("shared.assessment")
    except ModuleNotFoundError:
        return HOST_STATE_NAMES[state]
    enum = shared_assessment.AssessmentState
    name = HOST_STATE_NAMES[state]
    for member in enum:
        if member.name.upper() == name or str(member.value).upper() == name:
            return member
    raise PlatformError(
        ErrorCode.CONFLICT_STATE, f"host has no assessment state matching {name}"
    )


@dataclass
class HostTool:
    """Structurally identical to `backend.llm.Tool` (name, description, input_model,
    handler, definition()).

    Defined here so this package installs and tests without the backend's
    dependencies; the real gateway consumes tools by shape, and when `backend`
    is importable its own `Tool` is used instead.
    """

    name: str
    description: str
    input_model: type[Any]
    handler: Any

    def definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }


def _tool_class() -> type[Any]:
    import importlib

    try:
        return importlib.import_module("backend.llm").Tool
    except ModuleNotFoundError:
        return HostTool


def build_tools(spec: AgentSpec, ctx: ToolContext, registry: ToolRegistry, record: StepRecord) -> list[Any]:
    """Wrap each allowlisted tool for the host gateway, keeping enforcement here."""
    tool_cls = _tool_class()
    tools: list[Any] = []
    for name in registry.allowed_names(spec.name, spec.tools):
        definition = registry.get(name)
        if definition is None:  # pragma: no cover - allowlist and catalog agree
            continue
        tools.append(
            tool_cls(
                name=wire_name(name),
                description=definition.description,
                input_model=definition.args_model,
                handler=_handler(ctx, registry, record, name),
            )
        )
    return tools


def _handler(ctx: ToolContext, registry: ToolRegistry, record: StepRecord, name: str) -> Any:
    def run(args: Any) -> Any:
        payload: dict[str, Any]
        try:
            result = registry.invoke(ctx, wire_name(name), args.model_dump(mode="json"))
            payload = result.payload
            ok = result.ok
            error_code = str(payload.get("error")) if payload.get("error") else None
        except PlatformError as exc:
            ok = False
            error_code = exc.code.value
            payload = {
                "error": exc.code.value,
                "detail": exc.message,
                "note": "refused by the platform; this cannot be overridden",
            }
        record.tool_invocations.append(
            ToolInvocation(
                name=tool_name(name), args={}, ok=ok, error_code=error_code,
                summary={k: v for k, v in payload.items() if k in ("error", "detail")},
            )
        )
        return payload

    return run


# --------------------------------------------------------------------------- sink


@dataclass
class HostSink(AssessmentSink):
    """Mirrors every orchestration step into the host's store."""

    host: AssessmentHostLike
    commit_sha: str
    run_ids: dict[str, str] = field(default_factory=dict)
    recorded: list[str] = field(default_factory=list)

    def on_transition(self, src: AssessmentState, dst: AssessmentState, note: str) -> None:
        self.host.transition(_host_state(dst), note)
        if dst is AssessmentState.FUNCTIONAL_REVIEW and hasattr(self.host, "repo_id"):
            _functional_review(self.host)

    def on_finding(self, finding: FindingRecord) -> None:
        import importlib

        try:
            findings_module = importlib.import_module("shared.findings")
        except ModuleNotFoundError:  # pragma: no cover
            return
        hypothesis = finding.hypothesis
        evidence = [
            contract_export.evidence_ref(ref, producer="agent:scout")
            for ref in hypothesis.cited_spans
        ]
        record = findings_module.Finding(
            id=finding.finding_id,
            assessment_id=self.host.assessment_id,
            commit_sha=self.commit_sha,
            kind=findings_module.FindingKind.security,
            standards=_finding_standards(finding),
            title=hypothesis.title[:500],
            status=findings_module.FindingStatus.hypothesis,
            subject_refs=[hypothesis.entry_point_id or ""] if hypothesis.entry_point_id else [],
            expectation_ids=[
                contract_export.canonical_expectation_id(e) for e in hypothesis.expectation_ids
            ],
            evidence=evidence,
            confidence=contract_export.CONFIDENCE_SCORE[hypothesis.confidence],
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        self.host.record_finding(record, actor="agent:scout")
        self.host.record(finding.finding_id, contract_export.hypothesis(hypothesis, finding_id=finding.finding_id))
        self.recorded.append("finding")

    def on_record(self, finding: FindingRecord, record: Any, kind: str) -> None:
        mapped: Any | None = None
        if kind == "validation_result":
            try:
                mapped = contract_export.validation_result(record)
            except ValueError:
                # No executed run: cannot be represented canonically (gap 1).
                self.host.progress(
                    f"validation {record.outcome.value} has no executed check to record",
                    finding_id=finding.finding_id,
                )
                return
        elif kind == "attack_path":
            mapped = contract_export.attack_path(record)
            if hasattr(self.host, "record_standards"):
                self.host.record_standards(
                    finding.finding_id,
                    _finding_standards(finding),
                    severity=contract_export.severity(finding.severity) if finding.severity else None,
                )
        elif kind == "root_cause":
            mapped = contract_export.root_cause(record)
        elif kind == "remediation_plan":
            mapped = contract_export.remediation_plan(record)
        elif kind == "hardening_recommendation":
            mapped = _hardening(
                record,
                attack=[ref for step in finding.attack_path.steps for ref in step.attack]
                if finding.attack_path
                else [],
            )
        if mapped is not None:
            self.host.record(finding.finding_id, mapped)
            self.recorded.append(kind)

    def on_patch(self, finding: FindingRecord, candidate: Any, diff: str) -> None:
        artifact = self.host.store_text(diff)
        artifact_id = getattr(artifact, "id", None) or str(artifact)
        run_id = self.run_ids["patch"]
        self.host.record_patch(
            contract_export.patch_candidate(
                candidate,
                base_commit_sha=self.commit_sha,
                produced_by_run_id=run_id,
                rationale=finding.plan.strategy if finding.plan else "",
                diff_artifact_id=artifact_id,
            )
        )
        self.recorded.append("patch")

    def on_verification(self, finding: FindingRecord, result: Any) -> None:
        self.host.record_verification(
            contract_export.verification_result(
                result, produced_by_run_id=result.verify_run_id or self.run_ids["verify"]
            )
        )
        self.recorded.append("verification")

    def on_status(self, finding: FindingRecord, status: str) -> None:
        self.host.progress(f"finding {status}", finding_id=finding.finding_id, status=status)


def _hardening(record: Any, *, attack: list[Any] | None = None) -> Any:
    import importlib

    try:
        findings_module = importlib.import_module("shared.findings")
    except ModuleNotFoundError:  # pragma: no cover
        return None

    refs = {ref.id: ref for ref in record.d3fend}
    return findings_module.HardeningRecommendation(
        id=record.id,
        finding_id=record.finding_id,
        category=record.category,
        recommendation=record.recommendation[:500],
        effort=record.effort,
        d3fend=list(refs.values()),
    )


# --------------------------------------------------------------------------- orchestrator


@dataclass
class HostOrchestrator:
    """`security_agents.api:build_orchestrator()` result: `run(host)`.

    Production uses trusted repository bindings, the assessment's Git SHA, and
    the upstream intelligence service. Explicit development/test mode may use
    the labelled directory fixture adapter. Approval checkpoints persist typed
    finding records and baseline failures without sharing model conversations.
    """

    target_dir: Path | None = None
    labels_path: Path | None = None
    workdir: Path | None = None
    driver: SandboxDriver | None = None
    registry: ToolRegistry | None = None
    max_hypotheses: int = 3
    validate_count: int = 2
    intelligence_service: Any = None

    def run(self, host: AssessmentHostLike) -> None:
        target = self.target_dir or _env_path("SECURITY_AGENTS_TARGET_DIR")
        from .intel.host import bindings_path
        bound = bindings_path() is not None
        if not bound and target is None:
            raise PlatformError(
                ErrorCode.SNAPSHOT_NOT_READY,
                "no trusted checkout (REPOSITORY_BINDINGS_FILE); for dev/test set SECURITY_AGENTS_TARGET_DIR",
            )
        checkpoint = host.load_checkpoint("security_agents.approval.v1")
        resuming = str(getattr(host.assessment, "state", "")).upper() == "AWAITING_APPROVAL"
        if resuming and checkpoint is None:
            raise PlatformError(ErrorCode.CONFLICT_STATE, "approval checkpoint is missing")
        if checkpoint is not None and (
            checkpoint.get("version") != 1 or checkpoint.get("assessment_id") != host.assessment_id
        ):
            raise PlatformError(ErrorCode.CONFLICT_STATE, "invalid approval checkpoint identity/version")

        import tempfile

        base_workdir = self.workdir or _env_path("SECURITY_AGENTS_WORKDIR")
        if base_workdir is not None:
            base_workdir.mkdir(parents=True, exist_ok=True)
        workdir = Path(tempfile.mkdtemp(prefix=f"{host.assessment_id}-", dir=base_workdir))
        if bound:
            from .intel.host import bound_intelligence
            intel = bound_intelligence(host, workdir, self.intelligence_service)
        else:
            if os.environ.get("APP_ENV") not in {"development", "test"}:
                raise PlatformError(ErrorCode.SNAPSHOT_NOT_READY, "production host requires REPOSITORY_BINDINGS_FILE")
            intel = self._build_intel(
                target, workdir, snapshot_id=checkpoint.get("snapshot_id") if resuming else None, host=host
            )
        if resuming and checkpoint["commit_sha"] != intel.snapshot.commit_sha:
            raise PlatformError(ErrorCode.SNAPSHOT_NOT_READY, "approval snapshot changed")
        scope = _adapt_scope(host.scope, intel)
        if not scope.targets:
            raise PlatformError(ErrorCode.SCOPE_DENIED, "host scope has no authorized targets")
        config = OrchestratorConfig(
            assessment_id=host.assessment_id,
            project_id=getattr(host, "project_id", "prj_unknown"),
            org_id=getattr(host, "org_id", "org_unknown"),
            scope=scope,
            target_id=scope.targets[0].target_id,
            requested_by=scope.requested_by,
            budget=_adapt_budget(host.assessment),
            max_hypotheses=self.max_hypotheses,
            max_hypotheses_to_validate=self.validate_count,
        )
        registry = self.registry or default_registry()
        sink = HostSink(host=host, commit_sha=intel.snapshot.commit_sha)
        orchestrator = Orchestrator(
            config,
            intel=intel,
            gateway=_NullGateway(),  # host.llm() is the only provider path here
            driver=self.driver or _default_driver(),
            library=default_library(),
            workdir=workdir / "work",
            registry=registry,
            sink=sink,
            step_runner=HostStepRunner(host=host, tool_factory=build_tools, run_ids=sink.run_ids),
            approve_remediation=_approver(host),
            cancelled=lambda: _cancelled(host),
        )
        if resuming:
            orchestrator.state = AssessmentState.AWAITING_APPROVAL
            orchestrator.result.state = AssessmentState.AWAITING_APPROVAL
            orchestrator.result.findings = TypeAdapter(list[FindingRecord]).validate_python(checkpoint["findings"])
            orchestrator.result.usage = Usage.model_validate(checkpoint["usage"])
            orchestrator._baseline_failing = list(checkpoint["baseline_failing"])
            # Approval applies only while current scope remains valid.
            from .scope_guard import ActionRequest, check
            decision = check(scope, ActionRequest(action="assessment_start"), utcnow())
            if not decision.allowed:
                raise PlatformError(ErrorCode.SCOPE_DENIED, decision.reason_code)
            orchestrator.roe = orchestrator._issue_roe()
            self._resume(orchestrator, host)
            return
        # The host already performed the scope gate and the first transition.
        result = orchestrator.run()
        if result.state is AssessmentState.AWAITING_APPROVAL:
            host.save_checkpoint("security_agents.approval.v1", {
                "version": 1,
                "assessment_id": host.assessment_id,
                "commit_sha": intel.snapshot.commit_sha,
                "snapshot_id": intel.snapshot.snapshot_id,
                "findings": TypeAdapter(list[FindingRecord]).dump_python(result.findings, mode="json"),
                "usage": result.usage.model_dump(mode="json"),
                "baseline_failing": orchestrator._baseline_failing,
            })
            host.progress("awaiting human remediation approval")

    def _resume(self, orchestrator: Orchestrator, host: AssessmentHostLike) -> None:
        """Continue after a human decided, using the approvals the host holds."""
        orchestrator.approve_remediation = _approver(host)
        diagnosed = [f for f in orchestrator.result.findings if f.plan is not None]
        approved: list[FindingRecord] = []
        for finding in diagnosed:
            try:
                decision = _approver(host)(finding)
            except ApprovalPending:
                host.progress("awaiting human remediation approval")
                return
            if decision is not None and decision.decision == "approved":
                finding.approval = decision
                approved.append(finding)
        if not approved:
            orchestrator._goto(AssessmentState.REPORTING, "remediation declined")
            orchestrator._finish()
            return
        orchestrator._goto(AssessmentState.REMEDIATION)
        for finding in approved:
            orchestrator._run_remediation(finding)
        orchestrator._goto(AssessmentState.HARDENING)
        for finding in approved:
            if finding.status == "verified":
                orchestrator._run_fortify(finding)
        orchestrator._goto(AssessmentState.REPORTING)
        orchestrator._finish()

    def _build_intel(
        self, target: Path, workdir: Path, *, snapshot_id: str | None = None, host: Any = None
    ) -> CodeIntel:
        import json
        import shutil

        recipe_path = target / "build_recipe.json"
        source = target
        strip_prefix = None
        if recipe_path.is_file():
            recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
            if recipe.get("target_dir"):
                source = target / str(recipe["target_dir"])
                strip_prefix = f"{recipe['target_dir']}/"
        staging = workdir / "staging"
        copy_tree(source, staging)
        if recipe_path.is_file():
            shutil.copy2(recipe_path, staging / "build_recipe.json")
        snapshot = SnapshotHandle.from_directory(
            staging, workdir / "snapshot", snapshot_id=snapshot_id or new_id("snp"), repo_id="rep_host"
        )
        labels = self.labels_path or _env_path("SECURITY_AGENTS_LABELS")
        if labels is None and host is not None:
            from .intel.host_service import shared_host_intel

            shared = shared_host_intel(host, snapshot, _bindings())
            if shared is not None:
                return shared
        expectations = None
        if labels is not None:
            expectations = load_expectations(
                labels, snapshot_id=snapshot.snapshot_id, commit_sha=snapshot.commit_sha,
                strip_prefix=strip_prefix,
            )
        return LocalIntel(snapshot, expectations=expectations)


def _bindings() -> list[dict[str, Any]]:
    import json

    from .intel.host import bindings_path

    path = bindings_path()
    if not path or not Path(path).is_file():
        return []
    return list(json.loads(Path(path).read_text(encoding="utf-8")))


def _val(obj: Any, name: str) -> Any:
    attr = getattr(obj, name, None)
    return attr() if callable(attr) else attr


_PROPAGATE = {"CANCELLED", "BUDGET_EXHAUSTED", "SCOPE_DENIED"}


def _functional_review(host: Any) -> None:
    """Pillar 1 inside the assessment: Sai's reviewer on the same commit, persisting its own
    run and findings through the host. Unavailable/failing review is recorded and the
    security run continues; cancel/budget/scope errors propagate."""
    try:
        from code_review import api as review_api
    except ImportError:
        host.progress("functional review unavailable: code_review is not installed in this worker")
        return
    intent = _change_intent(host)
    try:
        try:
            outcome = review_api.review_assessment(host, change_intent=intent)
        except Exception as exc:
            if str(getattr(getattr(exc, "code", None), "value", "")) != "SNAPSHOT_NOT_READY":
                raise
            outcome = _review_without_snapshot(host, intent, review_api)
        result = outcome.result
        host.progress(
            f"functional review {result.status.value}: {len(result.findings)} functional finding(s)"
        )
    except Exception as exc:
        code = str(getattr(getattr(exc, "code", None), "value", type(exc).__name__))
        if code in _PROPAGATE:
            raise
        host.progress(f"functional review failed ({code}): {exc}"[:500])


def _review_without_snapshot(host: Any, intent: Any, review_api: Any) -> Any:
    """No indexed snapshot row for this commit: review the pinned checkout directly."""
    from shared.intelligence import SnapshotRef
    from shared.review import ReviewRequest

    a = _val(host, "assessment")
    request = ReviewRequest(
        assessment_id=a.id,
        snapshot_ref=SnapshotRef(
            project_id=a.project_id,
            repo_id=host.repo_id,
            commit_sha=a.commit_sha,
            snapshot_id=a.snapshot_id or new_id("snp"),
            index_version="checkout",
        ),
        change_intent=intent or _default_intent(a),
        budget=a.budget,
    )
    source = review_api.resolve_repo(host.repo_id, commit_sha=a.commit_sha)
    return review_api.review_full(host, request, source=source)


def _default_intent(a: Any) -> Any:
    from shared.review import ChangeIntent, ChangeIntentSource

    return ChangeIntent(
        source=ChangeIntentSource.manual, title=f"assessment of {a.commit_sha[:12]}", head_sha=a.commit_sha
    )


def _change_intent(host: Any) -> Any:
    """Push/PR intent (commit range, PR title/body as untrusted text) of the monitoring event
    that triggered this assessment; None for manual assessments."""
    a = _val(host, "assessment")
    if not getattr(a, "reassessment_request_id", None):
        return None
    try:
        import sqlalchemy as sa
        from backend.db import monitoring_events, reassessment_requests, transaction
        from shared.review import ChangeIntent, ChangeIntentSource
    except ImportError:
        return None
    with transaction() as conn:
        rrq = conn.execute(
            sa.select(reassessment_requests.c.doc).where(
                reassessment_requests.c.id == a.reassessment_request_id
            )
        ).scalar()
        ev = conn.execute(
            sa.select(monitoring_events.c.doc).where(
                monitoring_events.c.id == ((rrq or {}).get("event_ids") or [""])[0]
            )
        ).scalar()
    if not ev or not ev.get("commit_range"):
        return None
    kind = ChangeIntentSource.pull_request if ev.get("type") == "pull_request" else ChangeIntentSource.push
    return ChangeIntent(
        source=kind,
        title=f"{kind.value} {(ev.get('ref') or '')}"[:500],
        base_sha=ev["commit_range"].get("base_sha"),
        head_sha=a.commit_sha,
    )


class _NullGateway:
    """Placeholder gateway: in host mode every model call goes through the host."""

    mode = "host"

    def model_for(self, agent: AgentName) -> str:  # pragma: no cover - never called
        return "host"

    def complete(self, request: Any) -> Any:  # pragma: no cover - never called
        raise PlatformError(
            ErrorCode.CONFLICT_STATE, "host mode must route model calls through host.llm()"
        )

    def cost_usd(self, model: str, usage: Any) -> float:  # pragma: no cover
        return 0.0


def _default_driver() -> SandboxDriver:
    if (
        os.environ.get("APP_ENV") in {"development", "test"}
        and os.environ.get("SANDBOX_ALLOW_LOCAL_PROCESS") == "1"
    ):
        return LocalProcessDriver(allow=True)
    try:
        from backend.settings import get_settings
        settings = get_settings()
    except ImportError:
        settings = None
    if settings is not None and settings.security_sandbox == "local-dev":
        if settings.app_env not in {"development", "test"}:
            raise PlatformError(ErrorCode.SANDBOX_POLICY_VIOLATION, "local-dev sandbox outside development/test")
        return LocalProcessDriver(allow=True)
    return DockerSandboxDriver()


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else None


def _cancelled(host: AssessmentHostLike) -> bool:
    try:
        host.check_cancelled()  # type: ignore[attr-defined]
    except AttributeError:
        return False
    except Exception:
        return True
    return False


def _approver(host: AssessmentHostLike):
    """Approval policy: read the host's approvals; request one if none exists."""

    def approve(finding: FindingRecord) -> Approval | None:
        if finding.plan is None:
            return None
        subject_id = finding.plan.id
        for approval in host.approvals():
            if str(getattr(approval, "subject_id", "")) != subject_id:
                continue
            status = str(getattr(approval, "status", getattr(approval, "decision", ""))).lower()
            subject_type = str(getattr(approval, "subject_type", ""))
            if subject_type != "remediation":
                continue
            if status == "approved":
                actor = getattr(approval, "decided_by", None)
                if not actor or not str(actor).startswith("usr_"):
                    raise PlatformError(ErrorCode.APPROVAL_REQUIRED, "remediation requires an identified human approver")
                return Approval(
                    id=str(getattr(approval, "id", new_id("apv"))),
                    project_id=str(getattr(host, "project_id", "prj_unknown")),
                    subject_type="remediation",
                    subject_id=subject_id,
                    decision="approved",
                    decided_by=str(approval.decided_by),
                )
            if status in {"declined", "rejected"}:
                return Approval(
                    id=str(getattr(approval, "id", new_id("apv"))),
                    project_id=str(getattr(host, "project_id", "prj_unknown")),
                    subject_type="remediation",
                    subject_id=subject_id,
                    decision="declined",
                    decided_by=str(approval.decided_by),
                )
            raise ApprovalPending(finding.finding_id, str(getattr(approval, "id", "")))
        requested = host.request_approval(
            _approval_subject(), subject_id, f"remediate {finding.hypothesis.title}"[:500]
        )
        raise ApprovalPending(finding.finding_id, str(getattr(requested, "id", "")))

    return approve


def _approval_subject() -> Any:
    import importlib

    try:
        scope_module = importlib.import_module("shared.scope")
    except ModuleNotFoundError:
        return "remediation"
    for attr in ("ApprovalSubject", "ApprovalSubjectType"):
        enum = getattr(scope_module, attr, None)
        if enum is not None:
            return enum("remediation")
    return "remediation"


def _adapt_scope(host_scope: Any, intel: CodeIntel) -> Any:
    """Map the host's AuthorizedScope onto this package's scope model."""
    from .contracts import AuthorizedScope, ScopeStatus, ScopeTarget

    targets = []
    for index, target in enumerate(getattr(host_scope, "targets", []) or []):
        targets.append(
            ScopeTarget(
                target_id=str(
                    getattr(target, "target_id", None) or getattr(target, "id", None) or f"tgt_{index}"
                ),
                repo_id=str(getattr(target, "repo_id", None) or intel.snapshot.repo_id),
                build_recipe_ref=str(getattr(target, "build_recipe_ref", None) or "build_recipe.json"),
                exposed_ports=list(getattr(target, "exposed_ports", []) or []),
            )
        )
    raw_status = getattr(host_scope, "status", None)
    status_raw = str(getattr(raw_status, "value", raw_status)).lower()
    try:
        status = ScopeStatus(status_raw)
    except ValueError:
        status = ScopeStatus.PENDING
    approved_at = getattr(host_scope, "approved_at", None)
    return AuthorizedScope(
        id=str(getattr(host_scope, "id", new_id("scp"))),
        project_id=str(getattr(host_scope, "project_id", "prj_unknown")),
        name=str(getattr(host_scope, "name", "host scope")),
        targets=targets,
        allowed_check_categories=list(
            getattr(host_scope, "allowed_check_categories", None) or []
        ),
        status=status,
        requested_by=str(getattr(host_scope, "requested_by", None) or "usr_host"),
        approved_by=getattr(host_scope, "approved_by", None),
        approved_at=approved_at,
        expires_at=getattr(host_scope, "expires_at", None) or utcnow(),
        notes="adapted from the host scope",
    )


def _adapt_budget(assessment: Any) -> Budget:
    budget = getattr(assessment, "budget", None)
    if getattr(budget, "max_tokens", 1) <= 0 or getattr(budget, "max_usd", 1) <= 0:
        raise PlatformError(ErrorCode.BUDGET_EXHAUSTED, "host budget does not permit model calls")
    return Budget(
        max_tokens=int(getattr(budget, "max_tokens", 1_000_000)),
        max_usd=float(getattr(budget, "max_usd", 10.0)),
        max_wall_clock_s=float(getattr(budget, "max_wall_clock_s", 0) or 3600.0),
    )


def build_orchestrator(**kwargs: Any) -> HostOrchestrator:
    """Factory the backend worker loads (`ORCHESTRATOR_FACTORY`)."""
    return HostOrchestrator(**kwargs)


SPEC_TABLE = {name.value: spec.version for name, spec in ALL_SPECS.items()}


def _finding_standards(finding: FindingRecord) -> Any:
    from shared.standards import FindingStandards
    from standards.catalog import catalog_versions

    evidence = [
        contract_export.evidence_ref(ref, producer="agent:scout") for ref in finding.hypothesis.cited_spans
    ]
    confidence = contract_export.CONFIDENCE_SCORE[finding.hypothesis.confidence]
    return FindingStandards(
        cwe=contract_export.weakness_ref(
            finding.hypothesis.weakness_class, evidence=evidence, confidence=confidence
        ),
        attack=list({ref.id: ref for step in finding.attack_path.steps for ref in step.attack}.values()) if finding.attack_path else [],
        cvss=finding.severity.cvss if finding.severity else None,
        unmapped=[] if finding.attack_path and any(step.attack for step in finding.attack_path.steps) else ["ATT&CK: no reviewed check rule matched; coarse catalog chains require human review"],
        catalog_versions=catalog_versions(),
        classified_by="agent:security",
        classified_at=utcnow(),
        exploit_status="reproduced_in_sandbox"
        if finding.validation and finding.validation.outcome.value == "confirmed"
        else "not_tested",
    )
