"""Integration ports. The reviewer depends on these protocols, not on other owners' internals.

* ``ReviewHost`` — satisfied by ``backend.host.AssessmentHost`` (Srihith).
* ``IntelligencePort`` — satisfied by ``code_intelligence.api.IntelligenceService`` (Sarosh).
  Optional: when it is absent the tools say so instead of inventing expectations.
* ``SandboxPort`` — test execution. ``code_review.sandbox.LocalProcessSandbox`` is the
  local-dev implementation; Alan's Docker driver plugs in through the same port.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from shared.assessment import AgentName, AgentRun, AgentRunStatus, ToolCallRecord
from shared.errors import ErrorBody
from shared.evidence import ArtifactKind, ArtifactRef
from shared.findings import Finding, PatchCandidate
from shared.intelligence import BehavioralExpectation, ContextPack, ContextPackRequest, SnapshotRef
from shared.scope import Approval
from shared.tenancy import Usage


class ReviewHost(Protocol):
    assessment_id: str

    def llm(self) -> Any: ...

    def progress(self, message: str, *, agent: AgentName | None = None, **data: Any) -> None: ...

    def store_json(self, value: Any, kind: ArtifactKind = ...) -> ArtifactRef: ...

    def store_text(
        self, text: str, kind: ArtifactKind = ..., media_type: str = ...
    ) -> ArtifactRef: ...

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
    ) -> str: ...

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
    ) -> AgentRun: ...

    def record_finding(self, finding: Finding, *, actor: str) -> Finding: ...

    def record_patch(self, patch: PatchCandidate) -> PatchCandidate: ...

    def approvals(self) -> list[Approval]: ...


class IntelligencePort(Protocol):
    def build_context_pack(self, request: ContextPackRequest) -> ContextPack: ...

    def expectations(
        self, ref: SnapshotRef, subject: str | None = None, *, offset: int = 0, limit: int = 100
    ) -> list[BehavioralExpectation]: ...


@dataclass(frozen=True)
class CaseResult:
    nodeid: str
    outcome: str  # passed | failed | skipped | error
    phase: str  # collect | setup | call | teardown
    exc_type: str | None = None
    message: str = ""


@dataclass
class ExecResult:
    """One executed test command. Produced only by actually running a process."""

    command: list[str]
    exit_code: int | None
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool
    cases: list[CaseResult] = field(default_factory=list)
    driver: str = ""
    isolation_level: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "duration_s": round(self.duration_s, 3),
            "driver": self.driver,
            "isolation_level": self.isolation_level,
            "cases": [c.__dict__ for c in self.cases],
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


class SandboxPort(Protocol):
    name: str
    isolation_level: str

    def run_pytest(
        self, project_dir: Path, targets: Sequence[str], *, timeout_s: float
    ) -> ExecResult: ...


@dataclass(frozen=True)
class RepoSource:
    """A git repository the operator registered for review. ``subdir`` is the project root."""

    local_path: Path
    subdir: str = ""
