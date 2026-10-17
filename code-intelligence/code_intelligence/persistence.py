"""Agreed backend-owned payload port; no backend internals imported by intelligence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from shared.intelligence import SnapshotRef, SnapshotStats

from code_intelligence.models import IntelligenceError, StoredIndex


@dataclass(frozen=True)
class KeyPage:
    keys: list[str]
    cursor: str | None = None


class PayloadStore(Protocol):
    """All operations must enforce the complete SnapshotRef including project_id.

    Payload keys are immutable. Duplicate identical writes are idempotent; conflicting
    bytes fail. get_payload raises KeyError when absent. list_keys is bounded (1..500).
    mark_ready commits visibility only after all payloads have been durably written.
    The producer's encoding is UTF-8 JSON bytes; returned digest is lowercase SHA-256.
    """

    def put_payload(
        self, snapshot_ref: SnapshotRef, kind: str, key: str, payload: bytes
    ) -> str: ...
    def get_payload(self, snapshot_ref: SnapshotRef, kind: str, key: str) -> bytes: ...
    def list_keys(
        self,
        snapshot_ref: SnapshotRef,
        kind: str,
        prefix: str = "",
        limit: int = 100,
        cursor: str | None = None,
    ) -> KeyPage: ...
    def mark_ready(self, snapshot_ref: SnapshotRef, stats: SnapshotStats) -> None: ...
    def find_snapshot(
        self, project_id: str, repo_id: str, commit_sha: str, index_version: str
    ) -> SnapshotRef: ...


class PayloadIndexStore:
    """Adapts shared immutable artifact persistence to the engine's IndexStore port."""

    def __init__(self, payloads: PayloadStore) -> None:
        self.payloads = payloads

    def put(self, index: StoredIndex) -> None:
        payload = index.model_dump_json().encode()
        digest = self.payloads.put_payload(index.ref, "intelligence_index", "index.json", payload)
        if digest != hashlib.sha256(payload).hexdigest():
            raise IntelligenceError("Persistence returned incorrect payload digest")
        self.payloads.mark_ready(index.ref, index.snapshot.stats)

    def get(self, ref: SnapshotRef) -> StoredIndex:
        try:
            payload = self.payloads.get_payload(ref, "intelligence_index", "index.json")
        except KeyError as exc:
            raise IntelligenceError("SNAPSHOT_NOT_READY: exact version is not indexed") from exc
        index = StoredIndex.model_validate_json(payload)
        if index.ref != ref:
            raise IntelligenceError("Stale or mismatched payload SnapshotRef")
        return index

    def find(self, project_id: str, repo_id: str, sha: str, version: str) -> StoredIndex:
        try:
            ref = self.payloads.find_snapshot(project_id, repo_id, sha, version)
        except KeyError as exc:
            raise IntelligenceError("SNAPSHOT_NOT_READY: exact version is not indexed") from exc
        return self.get(ref)
