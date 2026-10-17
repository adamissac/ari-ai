"""The backend `AssessmentHost` integration (backend/INTEGRATION.md §Alan).

Driven against a fake host that implements the documented interface, with a
fake gateway whose `run_tool_loop` really executes the tools this package
passes it. That proves:

  * every agent turn goes through `host.llm()` — there is no second provider
    path in host mode;
  * tool permission enforcement still happens here (a denied tool is reported
    to the model, never executed);
  * state transitions, agent runs, findings, patches and verifications are
    mirrored into the host;
  * a remediation approval is requested and the orchestrator returns in
    `AWAITING_APPROVAL`, then completes on re-entry once the host holds an
    approval.

UNVERIFIED against the real backend: these tests do not run `backend.host`
(Postgres + artifact store). The shapes come from `backend/INTEGRATION.md` and
`backend/backend/{host,llm}.py` as of the merge recorded in the coordination
message.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from security_agents.contracts import AgentName, ErrorCode, PlatformError
from security_agents.host_adapter import HostOrchestrator, build_orchestrator
from security_agents.workflow import AssessmentState

from . import fake_agents
from .conftest import PAYMENTS_LITE_DIR

shared = pytest.importorskip("shared", reason="canonical shared package not importable")
import shared.assessment as shared_assessment  # noqa: E402
import shared.findings as shared_findings  # noqa: E402

SUBMIT = "submit_result"


# --------------------------------------------------------------------------- fakes


@dataclass
class FakeUsage:
    input_tokens: int = 100
    output_tokens: int = 50
    usd: float = 0.001


@dataclass
class FakeLoopResult:
    final: Any
    turns: int
    usage: FakeUsage
    tool_calls: list[Any]
    transcript: list[dict[str, Any]]
    model: str
    provider_mode: str


@dataclass
class FakeGateway:
    """Stands in for `backend.llm.LLMGateway`, running the scripted trajectories.

    It executes the handlers of the tools it is given, exactly as the real
    gateway does, so the registry's enforcement is exercised.
    """

    scripts: dict[AgentName, list]
    calls: list[dict[str, Any]] = field(default_factory=list)
    denied: list[str] = field(default_factory=list)

    def provider_mode(self) -> str:
        return "fake"

    def model_for(self, agent: str) -> str:
        return "claude-opus-5-5"

    def run_tool_loop(
        self, *, agent, system, user_content, tools, output_model, max_turns=12, max_tokens=16_000
    ):
        from security_agents.llm.types import LLMRequest

        registry = {t.name: t for t in tools}
        self.calls.append({"agent": agent, "system": system, "tools": sorted(registry)})
        script = self.scripts[AgentName(agent)]
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]
        transcript: list[dict[str, Any]] = []
        for turn in range(max_turns):
            request = LLMRequest(
                agent=AgentName(agent), model="fake", system=system, messages=messages,
                tools=[{"name": n} for n in registry], max_tokens=max_tokens,
            )
            step = script[min(turn, len(script) - 1)]
            fake_turn = step(request) if callable(step) else step
            results: list[dict[str, Any]] = []
            assistant: list[dict[str, Any]] = []
            if fake_turn.text:
                assistant.append({"type": "text", "text": fake_turn.text})
            for name, args in fake_turn.tool_calls:
                block_id = f"toolu_{turn}_{name}"
                assistant.append({"type": "tool_use", "id": block_id, "name": name, "input": args})
                if name == SUBMIT or name.startswith("submit_"):
                    messages.append({"role": "assistant", "content": assistant})
                    transcript.extend(assistant)
                    return FakeLoopResult(
                        final=output_model.model_validate(args),
                        turns=turn + 1,
                        usage=FakeUsage(),
                        tool_calls=[],
                        transcript=transcript,
                        model="fake:claude-opus-5-5",
                        provider_mode="fake",
                    )
                tool = registry.get(name)
                if tool is None:
                    # Same behaviour as the real gateway: deny, report back, continue.
                    self.denied.append(name)
                    payload: Any = {"error": ErrorCode.TOOL_NOT_ALLOWED.value, "tool": name}
                else:
                    payload = tool.handler(tool.input_model.model_validate(args))
                results.append(
                    {"type": "tool_result", "tool_use_id": block_id,
                     "content": json.dumps(payload, default=str)}
                )
            messages.append({"role": "assistant", "content": assistant})
            transcript.extend(assistant)
            if results:
                messages.append({"role": "user", "content": results})
        raise RuntimeError(f"{agent} did not submit within {max_turns} turns")


@dataclass
class FakeHost:
    """Implements the documented subset of `backend.host.AssessmentHost`."""

    assessment_id: str = "asm_01HOSTADAPTER"
    project_id: str = "prj_01HOSTADAPTER"
    org_id: str = "org_01HOSTADAPTER"
    gateway: FakeGateway | None = None
    states: list[str] = field(default_factory=list)
    runs: list[dict[str, Any]] = field(default_factory=list)
    finished: list[dict[str, Any]] = field(default_factory=list)
    findings: list[Any] = field(default_factory=list)
    records: list[tuple[str, Any]] = field(default_factory=list)
    patches: list[Any] = field(default_factory=list)
    verifications: list[Any] = field(default_factory=list)
    approval_requests: list[tuple[str, str]] = field(default_factory=list)
    stored: list[Any] = field(default_factory=list)
    progress_messages: list[str] = field(default_factory=list)
    _approvals: list[Any] = field(default_factory=list)
    cancelled: bool = False

    # -- state / events
    def assessment(self) -> Any:
        return type("A", (), {"budget": type("B", (), {"max_tokens": 2_000_000, "max_usd": 50.0, "max_wall_clock_s": 900.0})()})()

    def scope(self) -> Any:
        return type(
            "S", (),
            {
                "id": "scp_01HOSTADAPTER", "project_id": self.project_id, "name": "host scope",
                "status": "active", "requested_by": "usr_requester", "approved_by": "usr_approver",
                "approved_at": None, "expires_at": None,
                "allowed_check_categories": ["access_control.ownership", "input_validation.bounds"],
                "targets": [
                    type("T", (), {"target_id": "tgt_payments_lite", "repo_id": "rep_payments_lite",
                                   "build_recipe_ref": "build_recipe.json", "exposed_ports": [8000]})()
                ],
            },
        )()

    def approvals(self) -> list[Any]:
        return list(self._approvals)

    def approve_all(self) -> None:
        for _subject_type, subject_id in self.approval_requests:
            self._approvals.append(
                type("Ap", (), {"id": "apv_01HOSTADAPTER", "subject_id": subject_id,
                                "status": "approved", "decided_by": "usr_human"})()
            )

    def decline_all(self) -> None:
        for _subject_type, subject_id in self.approval_requests:
            self._approvals.append(
                type("Ap", (), {"id": "apv_01DECLINED", "subject_id": subject_id,
                                "status": "declined", "decided_by": "usr_human"})()
            )

    def transition(self, target: Any, message: str = "") -> Any:
        self.states.append(getattr(target, "value", str(target)))
        return self.assessment()

    def progress(self, message: str, *, agent: Any = None, **data: Any) -> None:
        self.progress_messages.append(message)

    def check_cancelled(self) -> None:
        if self.cancelled:
            raise RuntimeError("cancelled")

    # -- llm
    def llm(self) -> Any:
        assert self.gateway is not None
        return self.gateway

    # -- artifacts
    def store_text(self, text: str, *args: Any, **kwargs: Any) -> Any:
        self.stored.append(text)
        return type("Art", (), {"id": f"art_{len(self.stored):08d}", "sha256": "0" * 64})()

    def store_json(self, value: Any, kind: Any = None) -> Any:
        self.stored.append(value)
        return type("Art", (), {"id": f"art_{len(self.stored):08d}", "sha256": "0" * 64})()

    # -- runs
    def start_agent_run(self, agent: Any, step_key: str, **kwargs: Any) -> str:
        run_id = f"run_{len(self.runs):08d}HOST"
        self.runs.append({"id": run_id, "agent": getattr(agent, "value", str(agent)),
                          "step_key": step_key, **kwargs})
        return run_id

    def finish_agent_run(self, run_id: str, status: Any, **kwargs: Any) -> Any:
        self.finished.append({"id": run_id, "status": getattr(status, "value", str(status)), **kwargs})
        return None

    # -- records
    def record_finding(self, finding: Any, *, actor: str) -> Any:
        self.findings.append(finding)
        return finding

    def record(self, finding_id: str, record: Any) -> None:
        self.records.append((finding_id, record))

    def record_patch(self, patch: Any) -> Any:
        self.patches.append(patch)
        return patch

    def record_verification(self, result: Any) -> Any:
        self.verifications.append(result)
        return result

    def request_approval(self, subject_type: Any, subject_id: str, reason: str) -> Any:
        self.approval_requests.append((getattr(subject_type, "value", str(subject_type)), subject_id))
        return type("Ap", (), {"id": f"apv_{len(self.approval_requests):08d}"})()


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def host_and_orchestrator(tmp_path, monkeypatch):
    from security_agents.sandbox.driver import LocalProcessDriver

    target_root = tmp_path / "snapshot_source"
    # the scripted Patch agent needs the real source to build its fix from
    from security_agents.sandbox.workspace import copy_tree

    copy_tree(PAYMENTS_LITE_DIR / "target", target_root)
    scripts = fake_agents.all_scripts(target_root)
    gateway = FakeGateway(scripts=scripts)
    host = FakeHost(gateway=gateway)
    orchestrator = build_orchestrator(
        target_dir=PAYMENTS_LITE_DIR,
        labels_path=PAYMENTS_LITE_DIR / "labels.yaml",
        workdir=tmp_path / "work",
        driver=LocalProcessDriver(allow=True),
    )
    return host, orchestrator, gateway


# --------------------------------------------------------------------------- tests


def test_factory_returns_the_documented_shape():
    orchestrator = build_orchestrator()
    assert isinstance(orchestrator, HostOrchestrator)
    assert callable(orchestrator.run)


def test_missing_target_fails_with_a_clear_error(monkeypatch):
    monkeypatch.delenv("SECURITY_AGENTS_TARGET_DIR", raising=False)
    with pytest.raises(PlatformError) as exc:
        build_orchestrator().run(FakeHost(gateway=FakeGateway(scripts={})))
    assert exc.value.code is ErrorCode.SNAPSHOT_NOT_READY  # no bound checkout, no target dir
    assert "SECURITY_AGENTS_TARGET_DIR" in exc.value.message


def test_runs_the_pre_approval_phases_and_requests_approval(host_and_orchestrator):
    host, orchestrator, gateway = host_and_orchestrator
    orchestrator.run(host)

    assert host.states[:7] == [
        "SCOPE_CHECK", "INDEXING", "FUNCTIONAL_REVIEW", "RECON", "VALIDATION", "ANALYSIS",
        "DIAGNOSIS",
    ]
    assert host.states[7] == "AWAITING_APPROVAL"
    assert "COMPLETED" not in host.states, "must stop for the human decision"
    assert len(host.approval_requests) == 1
    subject_type, subject_id = host.approval_requests[0]
    assert subject_type == "remediation"
    assert subject_id.startswith("rmp_")
    assert any("awaiting human" in m for m in host.progress_messages)


def test_every_agent_turn_goes_through_the_host_gateway(host_and_orchestrator):
    host, orchestrator, gateway = host_and_orchestrator
    orchestrator.run(host)
    agents = [c["agent"] for c in gateway.calls]
    assert agents == ["scout", "probe", "trace", "diagnose"]
    # each role sends its own system instruction
    assert len({c["system"] for c in gateway.calls}) == 4
    # and its own tool list, built from the registry allowlist
    assert "checks__run_template" in dict(zip(agents, [c["tools"] for c in gateway.calls], strict=True))["probe"]
    assert "checks__run_template" not in dict(zip(agents, [c["tools"] for c in gateway.calls], strict=True))["scout"]
    assert gateway.denied == [], "no scripted call should hit an ungranted tool here"


def test_agent_runs_are_persisted_through_the_host(host_and_orchestrator):
    host, orchestrator, gateway = host_and_orchestrator
    orchestrator.run(host)
    assert [r["agent"] for r in host.runs] == ["scout", "probe", "trace", "diagnose"]
    assert all(r["provider_mode"] == "fake" for r in host.runs)
    assert all(r["model_id"] == "claude-opus-5-5" for r in host.runs)
    assert all(r["prompt_version"] == "0.1.0" for r in host.runs)
    assert [f["status"] for f in host.finished] == ["succeeded"] * 4
    assert all("transcript" in f for f in host.finished)


def test_findings_and_records_are_mirrored_as_canonical_models(host_and_orchestrator):
    host, orchestrator, gateway = host_and_orchestrator
    orchestrator.run(host)
    assert len(host.findings) == 1
    finding = host.findings[0]
    assert isinstance(finding, shared_findings.Finding)
    assert finding.kind is shared_findings.FindingKind.security
    assert finding.assessment_id == host.assessment_id
    kinds = [type(record).__name__ for _fid, record in host.records]
    assert "Hypothesis" in kinds
    assert "ValidationResult" in kinds
    assert "AttackPath" in kinds
    assert "RootCause" in kinds
    assert "RemediationPlan" in kinds


def test_resume_after_approval_completes_remediation_and_hardening(host_and_orchestrator):
    host, orchestrator, gateway = host_and_orchestrator
    orchestrator.run(host)
    host.approve_all()
    orchestrator.run(host)

    assert host.states[-4:] == ["REMEDIATION", "HARDENING", "REPORTING", "COMPLETED"]
    assert [r["agent"] for r in host.runs] == [
        "scout", "probe", "trace", "diagnose", "patch", "verify", "fortify",
    ]
    assert len(host.patches) == 1
    patch = host.patches[0]
    assert isinstance(patch, shared_findings.PatchCandidate)
    assert "payments_lite/app.py" in patch.files_changed
    assert patch.diff_artifact_id.startswith("art_")
    assert len(host.verifications) == 1
    verification = host.verifications[0]
    assert isinstance(verification, shared_findings.VerificationResult)
    assert verification.verdict is shared_findings.VerificationVerdict.accepted
    assert verification.produced_by_run_id != patch.produced_by_run_id, "Verify must be its own run"
    assert any("hardened" in m for m in host.progress_messages)


def test_declined_approval_reports_without_patching(host_and_orchestrator):
    host, orchestrator, gateway = host_and_orchestrator
    orchestrator.run(host)
    host.decline_all()
    orchestrator.run(host)
    assert host.states[-2:] == ["REPORTING", "COMPLETED"]
    assert not host.patches
    assert not any(r["agent"] == "patch" for r in host.runs)


def test_diff_is_stored_as_an_artifact_not_inline(host_and_orchestrator):
    host, orchestrator, gateway = host_and_orchestrator
    orchestrator.run(host)
    host.approve_all()
    orchestrator.run(host)
    diffs = [s for s in host.stored if isinstance(s, str) and s.startswith("diff --git")]
    assert diffs, "the candidate diff must be stored as an artifact"
    assert "require_owner(p.customer_id, customer)" in diffs[0]


def test_tool_denial_still_enforced_in_host_mode(tmp_path):
    """A model asking for an ungranted tool is refused here, not by the host."""
    from security_agents.llm import FakeTurn
    from security_agents.sandbox.driver import LocalProcessDriver
    from security_agents.sandbox.workspace import copy_tree

    target_root = tmp_path / "src"
    copy_tree(PAYMENTS_LITE_DIR / "target", target_root)
    scripts = fake_agents.all_scripts(target_root)
    # make Scout try a tool it does not have before submitting
    original = scripts[AgentName.SCOUT]
    scripts[AgentName.SCOUT] = [
        FakeTurn(tool_calls=[("worktree__write_file", {"path": "payments_lite/app.py", "content": "x"})]),
        *original,
    ]
    gateway = FakeGateway(scripts=scripts)
    host = FakeHost(gateway=gateway)
    build_orchestrator(
        target_dir=PAYMENTS_LITE_DIR,
        labels_path=PAYMENTS_LITE_DIR / "labels.yaml",
        workdir=tmp_path / "work",
        driver=LocalProcessDriver(allow=True),
    ).run(host)
    assert "worktree__write_file" in gateway.denied
    assert (PAYMENTS_LITE_DIR / "target" / "payments_lite" / "app.py").read_text().startswith('"""HTTP API')
    # the step still completed: a refusal is data for the model
    assert any(r["agent"] == "scout" for r in host.runs)
    assert next(f["status"] for f in host.finished) == "succeeded"


def test_host_state_names_cover_every_state():
    from security_agents.host_adapter import HOST_STATE_NAMES

    for state in AssessmentState:
        if state is AssessmentState.CREATED:
            continue  # the host creates the assessment itself
        assert state in HOST_STATE_NAMES, state
        member = shared_assessment.AssessmentState(HOST_STATE_NAMES[state])
        assert member.name == HOST_STATE_NAMES[state]
