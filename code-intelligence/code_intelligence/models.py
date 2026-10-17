"""Private persistence records. Public entities are imported from canonical shared V0."""

from __future__ import annotations

import hashlib

from pydantic import Field
from shared.base import RepoRelPath, StrictModel
from shared.intelligence import (
    BehavioralExpectation,
    CallEdge,
    EntryPoint,
    Snapshot,
    SnapshotRef,
    Symbol,
)

INDEX_VERSION = "python-ast-ts/0.1.0"


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode()).hexdigest()[:32]
    return f"{prefix}_{digest}"


class SourceFile(StrictModel):
    path: RepoRelPath
    blob_sha: str
    content_sha256: str
    language: str
    is_test: bool
    content: str


class ImportRecord(StrictModel):
    path: RepoRelPath
    line: int
    module: str
    name: str | None = None
    alias: str | None = None
    scope: str


class DependencyRecord(StrictModel):
    path: RepoRelPath
    name: str
    constraint: str


class IndexIssue(StrictModel):
    path: str
    reason: str


class StoredIndex(StrictModel):
    """One immutable revision; cross-subsystem fields retain shared model identity."""

    ref: SnapshotRef
    snapshot: Snapshot
    tree_sha: str
    tree_files: dict[str, str]
    files: list[SourceFile]
    symbols: list[Symbol]
    calls: list[CallEdge]
    imports: list[ImportRecord]
    entry_points: list[EntryPoint]
    expectations: list[BehavioralExpectation]
    dependencies: list[DependencyRecord] = Field(default_factory=list)
    issues: list[IndexIssue] = Field(default_factory=list)
    base_snapshot_id: str | None = None
    carried_from: dict[str, str] = Field(default_factory=dict)


class IntelligenceError(ValueError):
    """An explicit indexing/retrieval failure, never a fabricated empty success."""
