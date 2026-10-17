"""Code-intelligence contracts (producer: code-intelligence / Sarosh).

Everything is pinned to an exact snapshot (repo + commit SHA + index version) so
conclusions about an old commit are never silently reused for new code.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from shared.base import (
    CommitSha,
    Confidence,
    LongText,
    RepoRelPath,
    ShortText,
    StrictModel,
    UtcDatetime,
)
from shared.evidence import EvidenceRef
from shared.ids import (
    ContextPackId,
    EntryPointId,
    ExpectationId,
    FindingId,
    ProjectId,
    RepositoryId,
    SnapshotId,
    SymbolId,
)


class SnapshotStatus(StrEnum):
    pending = "pending"
    indexing = "indexing"
    ready = "ready"
    failed = "failed"


class SnapshotRef(StrictModel):
    project_id: ProjectId
    repo_id: RepositoryId
    commit_sha: CommitSha
    snapshot_id: SnapshotId
    index_version: ShortText


class SnapshotStats(StrictModel):
    files: int = Field(default=0, ge=0)
    symbols: int = Field(default=0, ge=0)
    call_edges: int = Field(default=0, ge=0)
    entry_points: int = Field(default=0, ge=0)
    expectations: int = Field(default=0, ge=0)


class Snapshot(StrictModel):
    id: SnapshotId
    repo_id: RepositoryId
    commit_sha: CommitSha
    status: SnapshotStatus
    index_version: ShortText
    base_snapshot_id: SnapshotId | None = None
    stats: SnapshotStats = Field(default_factory=SnapshotStats)
    error_message: ShortText | None = None
    created_at: UtcDatetime
    completed_at: UtcDatetime | None = None


class SymbolKind(StrEnum):
    module = "module"
    class_ = "class"
    function = "function"
    method = "method"


class Symbol(StrictModel):
    id: SymbolId
    snapshot_id: SnapshotId
    kind: SymbolKind
    qualified_name: ShortText
    path: RepoRelPath
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    signature: ShortText | None = None
    decorators: list[ShortText] = Field(default_factory=list)
    docstring: LongText | None = None


class CallResolution(StrEnum):
    exact = "exact"
    likely = "likely"
    unresolved = "unresolved"


class CallEdge(StrictModel):
    snapshot_id: SnapshotId
    caller_id: SymbolId
    callee_id: SymbolId | None = None
    callee_name: ShortText
    resolution: CallResolution


class EntryPointKind(StrEnum):
    http_route = "http_route"
    cli = "cli"
    job = "job"


class EntryPoint(StrictModel):
    id: EntryPointId
    snapshot_id: SnapshotId
    kind: EntryPointKind
    handler_symbol_id: SymbolId
    method: ShortText | None = None
    path_template: ShortText | None = None
    auth_dependencies: list[ShortText] = Field(default_factory=list)


class ExpectationKind(StrEnum):
    functional = "functional"
    authorization = "authorization"
    ownership = "ownership"
    validation = "validation"
    invariant = "invariant"
    error_handling = "error_handling"
    data_handling = "data_handling"
    performance = "performance"


class ExpectationOrigin(StrEnum):
    extracted = "extracted"  # deterministically derived from tests/specs/contracts
    inferred = "inferred"  # LLM-inferred; low confidence until confirmed
    human_input = "human_input"


class ExpectationStatus(StrEnum):
    confirmed = "confirmed"
    inferred = "inferred"
    ambiguous = "ambiguous"
    conflicting = "conflicting"
    rejected = "rejected"


class DataSensitivity(StrEnum):
    none = "none"
    internal = "internal"
    personal = "personal"
    financial = "financial"


class BehavioralExpectation(StrictModel):
    id: ExpectationId
    snapshot_id: SnapshotId
    subject_ref: ShortText = Field(description="sym_/ent_ id or qualified name")
    statement: ShortText
    kind: ExpectationKind
    sources: list[EvidenceRef] = Field(min_length=1)
    confidence: Confidence
    origin: ExpectationOrigin
    status: ExpectationStatus
    data_sensitivity: DataSensitivity | None = None


class ContextPurpose(StrEnum):
    review = "review"
    scout = "scout"
    probe = "probe"
    trace = "trace"
    diagnose = "diagnose"
    patch = "patch"
    fortify = "fortify"
    verify = "verify"
    monitoring = "monitoring"


class ContextPackRequest(StrictModel):
    snapshot_ref: SnapshotRef
    purpose: ContextPurpose
    focus: list[ShortText] = Field(
        default_factory=list, description="symbol ids, paths or entry points to center on"
    )
    token_budget: int = Field(default=24_000, ge=256, le=400_000)


class ContextChunk(StrictModel):
    provenance: EvidenceRef
    content: LongText
    trust: Literal["untrusted"] = "untrusted"
    token_estimate: int = Field(ge=0)


class ContextPack(StrictModel):
    id: ContextPackId
    snapshot_ref: SnapshotRef
    request: ContextPackRequest
    chunks: list[ContextChunk]
    token_budget: int = Field(ge=0)
    token_count: int = Field(ge=0)
    provenance: list[EvidenceRef] = Field(default_factory=list)
    created_at: UtcDatetime


class ImpactResolution(StrEnum):
    symbol = "symbol"  # code-intelligence diffed two indexed snapshots
    path_only = "path_only"  # fallback: only changed file paths are known


class ImpactSet(StrictModel):
    """What a commit range touches (docs/10 'Correlate')."""

    repo_id: RepositoryId
    base_sha: CommitSha | None = None
    head_sha: CommitSha
    base_snapshot_id: SnapshotId | None = None
    head_snapshot_id: SnapshotId | None = None
    resolution: ImpactResolution
    changed_paths: list[RepoRelPath] = Field(default_factory=list)
    symbols: list[SymbolId] = Field(default_factory=list)
    expectations: list[ExpectationId] = Field(default_factory=list)
    findings: list[FindingId] = Field(default_factory=list)
    regression_tests: list[ShortText] = Field(default_factory=list)
