"""TEST DOUBLES: an in-memory ReviewHost and helpers to script the FakeTransport.

The scripted "model" only decides which tool to call; every tool really executes
(git exports, file reads, pytest in the sandbox). This is replay/fake mode and is
never presented as live provider evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from typing import Any

from backend.llm import FakeTransport, LLMGateway, LLMTransport, build_gateway
from backend.settings import Settings
from shared.assessment import AgentName, AgentRun, AgentRunStatus, ToolCallRecord
from shared.base import utcnow
from shared.errors import ErrorBody
from shared.evidence import ArtifactKind, ArtifactRef
from shared.findings import Finding, PatchCandidate
from shared.ids import IdPrefix, new_id
from shared.intelligence import SnapshotRef
from shared.review import ChangeIntent, ChangeIntentSource, ReviewRequest
from shared.scope import Approval, ApprovalStatus, ApprovalSubject
from shared.tenancy import Budget, Usage


class InMemoryHost:
    def __init__(self, transport: LLMTransport) -> None:
        self.assessment_id = new_id(IdPrefix.asm)
        self.project_id = new_id(IdPrefix.prj)
        self.transport = transport
        self.artifacts: dict[str, tuple[ArtifactRef, bytes]] = {}
        self.runs: dict[str, AgentRun] = {}
        self.outputs: dict[str, Any] = {}
        self.transcripts: dict[str, Any] = {}
        self._findings: dict[str, Finding] = {}
        self.patches: list[PatchCandidate] = []
        self._approvals: list[Approval] = []
        self.events: list[str] = []
        self.usage = Usage()

    def llm(self) -> LLMGateway:
        settings = Settings(_env_file=None, anthropic_api_key=None)  # type: ignore[call-arg]
        return build_gateway(settings=settings, transport=self.transport, charge=self._charge)

    def _charge(self, u: Usage) -> None:
        self.usage = Usage(
            **{k: getattr(self.usage, k) + getattr(u, k) for k in Usage.model_fields}
        )

    def progress(self, message: str, *, agent: AgentName | None = None, **data: Any) -> None:
        self.events.append(message)

    def _put(self, data: bytes, kind: ArtifactKind, media: str) -> ArtifactRef:
        ref = ArtifactRef(
            id=new_id(IdPrefix.art),
            kind=kind,
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            media_type=media,
        )
        self.artifacts[ref.id] = (ref, data)
        return ref

    def store_json(self, value: Any, kind: ArtifactKind = ArtifactKind.tool_output) -> ArtifactRef:
        return self._put(
            json.dumps(value, sort_keys=True, default=str).encode(), kind, "application/json"
        )

    def store_text(
        self, text: str, kind: ArtifactKind = ArtifactKind.log, media_type: str = "text/plain"
    ) -> ArtifactRef:
        return self._put(text.encode(), kind, media_type)

    def read_artifact(self, artifact_id: str) -> bytes:
        return self.artifacts[artifact_id][1]

    def artifact_json(self, artifact_id: str) -> Any:
        return json.loads(self.read_artifact(artifact_id))

    def start_agent_run(
        self,
        agent,
        step_key,
        *,
        attempt=1,
        provider_mode,
        model_id,
        prompt_version,
        input_payload=None,
    ) -> str:  # noqa: E501
        rid = new_id(IdPrefix.run)
        self.runs[rid] = AgentRun(
            id=rid,
            assessment_id=self.assessment_id,
            agent=agent,
            step_key=step_key,
            attempt=attempt,
            status=AgentRunStatus.running,
            provider_mode=provider_mode,
            model_id=model_id,
            prompt_version=prompt_version,
            started_at=utcnow(),
        )
        return rid

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
        run = self.runs[run_id]
        assert run.status is AgentRunStatus.running, "run finished twice"
        self.runs[run_id] = run.model_copy(
            update={
                "status": status,
                "usage": usage or run.usage,
                "tool_calls": tool_calls or [],
                "error": error,
                "ended_at": utcnow(),
            }
        )
        self.outputs[run_id] = output
        self.transcripts[run_id] = transcript
        return self.runs[run_id]

    def record_finding(self, finding: Finding, *, actor: str) -> Finding:
        assert finding.assessment_id == self.assessment_id
        self._findings[finding.id] = finding
        return finding

    def findings(self) -> list[Finding]:
        return list(self._findings.values())

    def record_patch(self, patch: PatchCandidate) -> PatchCandidate:
        assert patch.finding_id in self._findings
        assert self.runs[patch.produced_by_run_id].agent is AgentName.reviewer
        self.patches.append(patch)
        return patch

    def approvals(self) -> list[Approval]:
        return list(self._approvals)

    def approve(
        self, finding_id: str, *, status: ApprovalStatus = ApprovalStatus.approved
    ) -> Approval:
        ap = Approval(
            id=new_id(IdPrefix.apv),
            project_id=self.project_id,
            subject_type=ApprovalSubject.remediation,
            subject_id=finding_id,
            status=status,
            requested_at=utcnow(),
            decided_at=utcnow(),
        )
        self._approvals.append(ap)
        return ap


def make_request(host: Any, sc: Any, *, source: ChangeIntentSource | None = None) -> ReviewRequest:
    return ReviewRequest(
        assessment_id=host.assessment_id,
        snapshot_ref=SnapshotRef(
            project_id=getattr(host, "project_id", new_id(IdPrefix.prj)),
            repo_id="rep_fixture0001",
            commit_sha=sc.head_sha,
            snapshot_id="snp_fixture0001",
            index_version="fixture",
        ),
        change_intent=ChangeIntent(
            source=source
            or (ChangeIntentSource.pull_request if sc.base_sha else ChangeIntentSource.manual),
            title=sc.title,
            body=sc.body,
            base_sha=sc.base_sha,
            head_sha=sc.head_sha,
        ),
        budget=Budget(),
    )


# ------------------------------------------------------------ scripting

_counter = [0]


def call(tool: str, /, **inp: Any) -> dict[str, Any]:
    _counter[0] += 1
    return {
        "content": [
            {"type": "text", "text": f"Next I will call {tool}."},
            {"type": "tool_use", "id": f"toolu_{_counter[0]:05d}", "name": tool, "input": inp},
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 900, "output_tokens": 120},
    }


def all_tool_results(request: dict[str, Any]) -> str:
    out = []
    for m in request["messages"]:
        if m["role"] == "user" and isinstance(m["content"], list):
            for b in m["content"]:
                if b.get("type") == "tool_result":
                    c = b.get("content")
                    out.append(c if isinstance(c, str) else json.dumps(c))
    return "\n".join(out)


def written_ids(request: dict[str, Any]) -> list[str]:
    return re.findall(r"test_id=(tst_[0-9A-Za-z]+)\.", all_tool_results(request))


def dyn(
    fn: Callable[[dict[str, Any]], dict[str, Any]],
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    return fn


def fake(script: list[Any]) -> FakeTransport:
    return FakeTransport(script)
