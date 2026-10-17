"""Durable, atomic local store behind a port owned by intelligence.

SQLite is the local development adapter. Backend PostgreSQL integration must supply
this same port; this module deliberately imports no backend internals.
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Protocol

from shared.intelligence import SnapshotRef

from code_intelligence.models import IntelligenceError, StoredIndex


class IndexStore(Protocol):
    def put(self, index: StoredIndex) -> None: ...
    def get(self, ref: SnapshotRef) -> StoredIndex: ...
    def find(self, project_id: str, repo_id: str, sha: str, version: str) -> StoredIndex: ...


class SQLiteIndexStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with closing(self._connect()) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""CREATE TABLE IF NOT EXISTS intelligence_indexes (
                snapshot_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, repo_id TEXT NOT NULL,
                commit_sha TEXT NOT NULL, index_version TEXT NOT NULL, doc TEXT NOT NULL,
                sha256 TEXT NOT NULL, UNIQUE(project_id, repo_id, commit_sha, index_version))""")
            conn.commit()
        self.path.chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=30)

    def put(self, index: StoredIndex) -> None:
        payload = index.model_dump_json()
        digest = hashlib.sha256(payload.encode()).hexdigest()
        ref = index.ref
        with closing(self._connect()) as conn, conn:
            existing = conn.execute(
                "SELECT sha256 FROM intelligence_indexes WHERE snapshot_id = ?",
                (ref.snapshot_id,),
            ).fetchone()
            if existing:
                if existing[0] != digest:
                    raise IntelligenceError(
                        "Immutable snapshot already exists with different content"
                    )
                return
            try:
                conn.execute(
                    "INSERT INTO intelligence_indexes VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        ref.snapshot_id,
                        ref.project_id,
                        ref.repo_id,
                        ref.commit_sha,
                        ref.index_version,
                        payload,
                        digest,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise IntelligenceError("Snapshot version key already registered") from exc

    @staticmethod
    def _decode(row: tuple[str, str] | None) -> StoredIndex:
        if row is None:
            raise IntelligenceError("SNAPSHOT_NOT_READY: exact version is not indexed")
        payload, digest = row
        if hashlib.sha256(payload.encode()).hexdigest() != digest:
            raise IntelligenceError("Stored index failed integrity verification")
        return StoredIndex.model_validate_json(payload)

    def get(self, ref: SnapshotRef) -> StoredIndex:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT doc, sha256 FROM intelligence_indexes WHERE snapshot_id=? AND project_id=?",
                (ref.snapshot_id, ref.project_id),
            ).fetchone()
        index = self._decode(row)
        if index.ref != ref:
            raise IntelligenceError("Stale or mismatched SnapshotRef")
        return index

    def find(self, project_id: str, repo_id: str, sha: str, version: str) -> StoredIndex:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT doc, sha256 FROM intelligence_indexes "
                "WHERE project_id=? AND repo_id=? AND commit_sha=? AND index_version=?",
                (project_id, repo_id, sha, version),
            ).fetchone()
        return self._decode(row)
