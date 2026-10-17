"""Server-sent event payloads for live assessment progress (docs/13 "SSE event shape").

Each event has a durable, per-assessment monotonically increasing ``seq`` that is
also the SSE ``id:`` field, so a reconnecting client sends ``Last-Event-ID`` and
receives exactly the events it missed; nothing is synthesized on reconnect.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from shared.assessment import AgentName, AssessmentState
from shared.base import JsonObject, ShortText, StrictModel, UtcDatetime
from shared.ids import AgentRunId, ApprovalId, AssessmentId, FindingId


class StreamEventType(StrEnum):
    state_changed = "assessment.state_changed"
    progress = "assessment.progress"
    agent_run_started = "agent_run.started"
    agent_run_finished = "agent_run.finished"
    finding_updated = "finding.updated"
    approval_requested = "approval.requested"
    completed = "assessment.completed"
    failed = "assessment.failed"


class StreamEvent(StrictModel):
    seq: int = Field(ge=1)
    assessment_id: AssessmentId
    type: StreamEventType
    state: AssessmentState | None = None
    agent: AgentName | None = None
    agent_run_id: AgentRunId | None = None
    finding_id: FindingId | None = None
    approval_id: ApprovalId | None = None
    message: ShortText
    data: JsonObject = Field(default_factory=dict)
    at: UtcDatetime
