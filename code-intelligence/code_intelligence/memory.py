"""Append-only exact-version annotations; immutable source indexes stay untouched."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Protocol

from shared.evidence import EvidenceKind, EvidenceRef
from shared.intelligence import (
    BehavioralExpectation,
    ExpectationOrigin,
    ExpectationStatus,
    SnapshotRef,
)
from shared.intelligence_memory import ExpectationDecision, VerifiedRegression

from code_intelligence.models import IntelligenceError


class MemoryConflict(IntelligenceError):
    """Optimistic revision conflict or attempted immutable regression overwrite."""


def ref_key(ref: SnapshotRef) -> str:
    return hashlib.sha256(ref.model_dump_json().encode()).hexdigest()


def same_decision(left: ExpectationDecision, right: ExpectationDecision) -> bool:
    return left.model_dump(exclude={"decided_at"}) == right.model_dump(exclude={"decided_at"})


class MemoryStore(Protocol):
    def put_decision(self, decision: ExpectationDecision) -> ExpectationDecision: ...
    def decisions(self, ref: SnapshotRef) -> list[ExpectationDecision]: ...
    def history(
        self, ref: SnapshotRef, expectation_id: str, *, after: int = 0, limit: int = 100
    ) -> list[ExpectationDecision]: ...
    def put_regression(self, record: VerifiedRegression) -> None: ...
    def regressions(self, ref: SnapshotRef) -> list[VerifiedRegression]: ...


class SQLiteMemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS expectation_decisions (
                    ref_key TEXT NOT NULL, expectation_id TEXT NOT NULL,
                    revision INTEGER NOT NULL, doc TEXT NOT NULL,
                    PRIMARY KEY(ref_key, expectation_id, revision));
                CREATE TABLE IF NOT EXISTS verified_regressions (
                    patch_id TEXT PRIMARY KEY, ref_key TEXT NOT NULL, doc TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS verified_regressions_ref
                    ON verified_regressions(ref_key);
            """)
            conn.commit()
        path.chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=30)

    def put_decision(self, decision: ExpectationDecision) -> ExpectationDecision:
        decision = ExpectationDecision.model_validate(decision.model_dump())
        key = ref_key(decision.snapshot_ref)
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT doc FROM expectation_decisions WHERE ref_key=? AND "
                "expectation_id=? ORDER BY revision DESC LIMIT 1",
                (key, decision.expectation_id),
            ).fetchone()
            previous = ExpectationDecision.model_validate_json(row[0]) if row else None
            if previous and same_decision(previous, decision):
                return previous
            if (previous.revision if previous else 0) != decision.expected_revision:
                raise MemoryConflict("CONFLICT_STATE: expectation decision revision changed")
            conn.execute(
                "INSERT INTO expectation_decisions VALUES (?, ?, ?, ?)",
                (key, decision.expectation_id, decision.revision, decision.model_dump_json()),
            )
        return decision

    def decisions(self, ref: SnapshotRef) -> list[ExpectationDecision]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT d.doc FROM expectation_decisions d JOIN (SELECT "
                "expectation_id, MAX(revision) AS revision FROM expectation_decisions "
                "WHERE ref_key=? GROUP BY expectation_id) latest ON "
                "latest.expectation_id=d.expectation_id AND latest.revision=d.revision "
                "WHERE d.ref_key=? ORDER BY d.expectation_id",
                (ref_key(ref), ref_key(ref)),
            ).fetchall()
        return [ExpectationDecision.model_validate_json(r[0]) for r in rows]

    def history(
        self, ref: SnapshotRef, expectation_id: str, *, after: int = 0, limit: int = 100
    ) -> list[ExpectationDecision]:
        if after < 0 or not 1 <= limit <= 500:
            raise IntelligenceError("Invalid decision history pagination")
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT doc FROM expectation_decisions WHERE ref_key=? AND "
                "expectation_id=? AND revision>? ORDER BY revision LIMIT ?",
                (ref_key(ref), expectation_id, after, limit),
            ).fetchall()
        return [ExpectationDecision.model_validate_json(r[0]) for r in rows]

    def put_regression(self, record: VerifiedRegression) -> None:
        record = VerifiedRegression.model_validate(record.model_dump())
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT doc FROM verified_regressions WHERE patch_id=?", (record.patch_id,)
            ).fetchone()
            if row:
                old = VerifiedRegression.model_validate_json(row[0])
                if old.model_dump(exclude={"created_at"}) != record.model_dump(
                    exclude={"created_at"}
                ):
                    raise MemoryConflict("CONFLICT_STATE: regression evidence is immutable")
                return
            conn.execute(
                "INSERT INTO verified_regressions VALUES (?, ?, ?)",
                (record.patch_id, ref_key(record.snapshot_ref), record.model_dump_json()),
            )

    def regressions(self, ref: SnapshotRef) -> list[VerifiedRegression]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT doc FROM verified_regressions WHERE ref_key=? ORDER BY patch_id",
                (ref_key(ref),),
            ).fetchall()
        return [VerifiedRegression.model_validate_json(r[0]) for r in rows]


def apply_decisions(
    expectations: list[BehavioralExpectation], decisions: list[ExpectationDecision]
) -> list[BehavioralExpectation]:
    by_id = {d.expectation_id: d for d in decisions}
    result = []
    for expectation in expectations:
        decision = by_id.get(expectation.id)
        if decision is None:
            result.append(expectation)
            continue
        if expectation.snapshot_id != decision.snapshot_ref.snapshot_id:
            raise IntelligenceError("Stale decision does not match expectation snapshot")
        evidence = EvidenceRef(
            kind=EvidenceKind.human_input,
            commit_sha=decision.snapshot_ref.commit_sha,
            provenance=f"authenticated-human:{decision.decided_by}:revision:{decision.revision}",
            note=decision.reason,
        )
        result.append(
            BehavioralExpectation.model_validate(
                {
                    **expectation.model_dump(),
                    "status": ExpectationStatus(decision.status),
                    "origin": ExpectationOrigin.human_input,
                    "sources": [*expectation.sources, evidence],
                }
            )
        )
    return result
