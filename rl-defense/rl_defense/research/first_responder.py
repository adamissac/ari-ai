"""Fixture-only first-responder proposal. No dispatcher, environment or authority API."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator
from shared.assessment import AgentRun, AgentRunStatus, AgentStepResult
from shared.base import Sha256Hex, UtcDatetime
from shared.evidence import EvidenceRef
from shared.ids import AssessmentId, IncidentId, ProjectId, RepositoryId
from shared.intelligence import SnapshotRef
from shared.scope import AuthorizedScope, ScopeStatus


class Action(StrEnum):
    abstain = "abstain"
    monitor = "continue_monitoring"
    scout = "request_scout"
    trace = "request_trace"
    diagnose = "request_diagnose"
    fortify = "request_fortify"
    notify = "request_analyst_notification"
    escalate = "request_escalation"
    route = "recommend_route_limit"
    source = "recommend_source_limit"
    containment = "request_containment_approval"
    stop = "request_stop_investigation"


ACTIONS = tuple(Action)
INVESTIGATION = frozenset({Action.scout, Action.trace, Action.diagnose, Action.fortify})
FEATURES = (
    "incident_age_seconds",
    "suspicious_count",
    "severity_indicator",
    "verified_findings",
    "pending_tasks",
    "remaining_budget_usd",
    "active_controls",
    "analyst_acknowledged",
    "completed_agent_runs",
    "failed_agent_runs",
    "terminal_run_cost_usd",
)
FactName = Literal[
    "incident_age_seconds",
    "suspicious_count",
    "severity_indicator",
    "verified_findings",
    "pending_tasks",
    "remaining_budget_usd",
    "active_controls",
    "analyst_acknowledged",
]


class Internal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)


class Stamp(Internal):
    receipt_id: str = Field(min_length=1, max_length=120)
    clock_id: str = Field(min_length=1, max_length=120)
    project_id: ProjectId
    repo_id: RepositoryId
    assessment_id: AssessmentId
    incident_id: IncidentId
    snapshot: SnapshotRef | None = None
    observed_at: UtcDatetime
    available_at: UtcDatetime
    available_seq: int = Field(ge=0)
    valid_until: UtcDatetime
    evidence: tuple[EvidenceRef, ...] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def ordered(self) -> Stamp:
        if self.observed_at > self.available_at or self.valid_until <= self.available_at:
            raise ValueError("invalid receipt availability/expiry")
        return self


class Fact(Internal):
    stamp: Stamp
    name: FactName
    value: float = Field(ge=0)

    @model_validator(mode="after")
    def domain(self) -> Fact:
        if self.name == "analyst_acknowledged" and self.value not in (0.0, 1.0):
            raise ValueError("acknowledgement must be an observed boolean")
        if (
            self.name
            in ("suspicious_count", "verified_findings", "pending_tasks", "active_controls")
            and not self.value.is_integer()
        ):
            raise ValueError("count must be integral")
        return self


class Capability(Internal):
    stamp: Stamp
    action: Action
    enabled: bool = False
    input_ready: bool = False
    budget_ready: bool = False
    host_gate_ready: bool = False
    destination_allowlisted: bool = False


class ScopeReceipt(Internal):
    stamp: Stamp
    scope: AuthorizedScope


class ResultReceipt(Internal):
    stamp: Stamp
    result: AgentStepResult
    run: AgentRun
    usage_attested: bool = False  # Usage defaults do not prove measured zero cost.

    @model_validator(mode="after")
    def result_binding(self) -> ResultReceipt:
        if (
            self.run.id != self.result.agent_run_id
            or self.run.agent != self.result.agent
            or self.run.status != self.result.status
            or self.run.assessment_id != self.stamp.assessment_id
            or self.run.usage != self.result.usage
        ):
            raise ValueError("agent run/result/context mismatch")
        if self.run.status in (
            AgentRunStatus.succeeded,
            AgentRunStatus.failed,
            AgentRunStatus.cancelled,
        ):
            if (
                self.run.ended_at is None
                or not self.run.started_at <= self.run.ended_at <= self.stamp.observed_at
            ):
                raise ValueError("terminal result lacks valid completion time")
        if self.run.status is AgentRunStatus.succeeded and self.run.output_artifact_id is None:
            raise ValueError("succeeded run needs output artifact provenance")
        return self


class Frame(Internal):
    version: Literal["first-responder-frame/0.1-proposal"] = "first-responder-frame/0.1-proposal"
    fixture_only: Literal[True] = True
    integration_agreed: bool = False
    clock_id: str
    project_id: ProjectId
    repo_id: RepositoryId
    assessment_id: AssessmentId
    incident_id: IncidentId
    snapshot: SnapshotRef | None = None
    cutoff_at: UtcDatetime
    cutoff_seq: int = Field(ge=1)
    deployment_binding: Stamp | None = None
    facts: tuple[Fact, ...] = Field(default=(), max_length=128)
    capabilities: tuple[Capability, ...] = Field(default=(), max_length=64)
    scopes: tuple[ScopeReceipt, ...] = Field(default=(), max_length=16)
    results: tuple[ResultReceipt, ...] = Field(default=(), max_length=64)


@dataclass(frozen=True)
class Observation:
    version: str
    context: tuple[str, str, str, str]
    snapshot_json: str | None
    cutoff_at: datetime
    cutoff_seq: int
    values: tuple[float, ...]
    known: tuple[bool, ...]
    mask: tuple[bool, ...]
    receipt_ids: tuple[str, ...]
    evidence_digests: tuple[str, ...]


def observe(frame: Frame) -> Observation:
    """Only trusted-fixture receipts; this mask never authorizes real execution."""
    context = (frame.project_id, frame.repo_id, frame.assessment_id, frame.incident_id)
    if frame.snapshot is not None and (
        frame.snapshot.project_id != frame.project_id or frame.snapshot.repo_id != frame.repo_id
    ):
        raise ValueError("snapshot context mismatch")
    seen: set[str] = set()
    used: list[Stamp] = []

    def visible(stamp: Stamp) -> bool:
        if not (
            stamp.observed_at < frame.cutoff_at
            and stamp.available_at < frame.cutoff_at
            and stamp.available_seq < frame.cutoff_seq
        ):
            return False
        if (stamp.project_id, stamp.repo_id, stamp.assessment_id, stamp.incident_id) != context:
            raise ValueError("foreign decision context")
        if stamp.clock_id != frame.clock_id:
            raise ValueError("incomparable availability clocks")
        if stamp.receipt_id in seen:
            raise ValueError("duplicate receipt identity")
        seen.add(stamp.receipt_id)
        if frame.snapshot is not None and stamp.snapshot != frame.snapshot:
            raise ValueError("snapshot mismatch")
        used.append(stamp)
        return True

    latest: dict[str, Fact] = {}
    for fact in frame.facts:
        if visible(fact.stamp):
            previous = latest.get(fact.name)
            if previous is not None and previous.stamp.available_seq == fact.stamp.available_seq:
                raise ValueError("ambiguous feature revision")
            if previous is None or previous.stamp.available_seq < fact.stamp.available_seq:
                latest[fact.name] = fact
    values = {
        name: fact.value
        for name, fact in latest.items()
        if frame.cutoff_at < fact.stamp.valid_until
    }
    terminal = [
        r
        for r in frame.results
        if visible(r.stamp)
        and frame.cutoff_at < r.stamp.valid_until
        and r.result.status
        in (AgentRunStatus.succeeded, AgentRunStatus.failed, AgentRunStatus.cancelled)
    ]
    run_ids = [r.result.agent_run_id for r in terminal]
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("duplicate terminal agent result")
    # These count terminal receipts only, never usefulness/confidence or security benefit.
    if terminal:
        values["completed_agent_runs"] = float(
            sum(r.result.status is AgentRunStatus.succeeded for r in terminal)
        )
        values["failed_agent_runs"] = float(
            sum(r.result.status is not AgentRunStatus.succeeded for r in terminal)
        )
        if any(r.usage_attested and not math.isfinite(r.result.usage.usd) for r in terminal):
            raise ValueError("invalid attested usage")
        if all(r.usage_attested for r in terminal):
            values["terminal_run_cost_usd"] = sum(r.result.usage.usd for r in terminal)
    scopes = [s for s in frame.scopes if visible(s.stamp)]
    if len({s.stamp.available_seq for s in scopes}) != len(scopes):
        raise ValueError("ambiguous scope revision")
    selected_scope = max(scopes, key=lambda s: s.stamp.available_seq) if scopes else None
    scope = (
        selected_scope.scope
        if selected_scope and frame.cutoff_at < selected_scope.stamp.valid_until
        else None
    )
    scoped = bool(
        scope is not None
        and scope.project_id == frame.project_id
        and scope.status is ScopeStatus.active
        and scope.approved_by is not None
        and scope.approved_at is not None
        and scope.approved_at < frame.cutoff_at < scope.expires_at
        and any(t.repo_id == frame.repo_id for t in scope.targets)
    )
    bound = bool(
        frame.snapshot is not None
        and frame.deployment_binding is not None
        and visible(frame.deployment_binding)
        and frame.cutoff_at < frame.deployment_binding.valid_until
        and frame.deployment_binding.snapshot == frame.snapshot
    )
    if not bound:
        values.pop("verified_findings", None)
    caps: dict[Action, Capability] = {}
    for cap in frame.capabilities:
        if visible(cap.stamp):
            old = caps.get(cap.action)
            if old is not None and old.stamp.available_seq == cap.stamp.available_seq:
                raise ValueError("ambiguous capability revision")
            if old is None or old.stamp.available_seq < cap.stamp.available_seq:
                caps[cap.action] = cap
    mask = []
    for action in ACTIONS:
        if action in (Action.abstain, Action.monitor):
            mask.append(True)
            continue
        chosen_cap = caps.get(action)
        allowed = bool(
            frame.integration_agreed
            and bound
            and scoped
            and chosen_cap is not None
            and frame.cutoff_at < chosen_cap.stamp.valid_until
            and chosen_cap.enabled
            and chosen_cap.input_ready
            and chosen_cap.budget_ready
            and chosen_cap.host_gate_ready
        )
        if action in (Action.notify, Action.escalate):
            allowed = allowed and chosen_cap is not None and chosen_cap.destination_allowlisted
        mask.append(allowed)
    return Observation(
        "first-responder-observation/0.1-proposal",
        context,
        frame.snapshot.model_dump_json() if frame.snapshot else None,
        frame.cutoff_at,
        frame.cutoff_seq,
        tuple(float(values.get(k, 0.0)) for k in FEATURES),
        tuple(k in values for k in FEATURES),
        tuple(mask),
        tuple(sorted(s.receipt_id for s in used)),
        tuple(
            sorted(
                {
                    hashlib.sha256(e.model_dump_json().encode()).hexdigest()
                    for s in used
                    for e in s.evidence
                }
            )
        ),
    )


class Decision(Internal):
    version: Literal["first-responder-decision/0.1-proposal"] = (
        "first-responder-decision/0.1-proposal"
    )
    action: Action
    observation_sha256: Sha256Hex
    issued_seq: int = Field(ge=1)
    issued_at: UtcDatetime
    behavior_policy: str = Field(min_length=1, max_length=120)
    behavior_probability: float | None = Field(default=None, gt=0, le=1)
    executed: Literal[False] = False
    training_eligible: Literal[False] = False


def observation_digest(observation: Observation) -> str:
    return hashlib.sha256(
        json.dumps(asdict(observation), sort_keys=True, default=str, allow_nan=False).encode()
    ).hexdigest()


def validate_proposal(observation: Observation, decision: Decision) -> None:
    if decision.observation_sha256 != observation_digest(observation):
        raise ValueError("decision observation binding mismatch")
    if decision.issued_seq <= observation.cutoff_seq or decision.issued_at < observation.cutoff_at:
        raise ValueError("decision must follow its cutoff")
    if not observation.mask[ACTIONS.index(decision.action)]:
        raise ValueError("infeasible proposal; no silent noop substitution")


class EvaluationPolicy(Protocol):
    def propose(self, observation: Observation) -> Decision: ...
