"""PostgreSQL companion memory for immutable intelligence indexes."""

from __future__ import annotations

import hashlib

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from backend import audit
from backend.api.deps import org_role
from backend.db import get_engine, index_snapshots, metadata, projects, repositories
from shared.audit import ActorType
from shared.intelligence import SnapshotRef
from shared.intelligence_memory import ExpectationDecision, VerifiedRegression
from shared.tenancy import MemberRole

expectation_decisions = sa.Table(
    "expectation_decisions",
    metadata,
    sa.Column("ref_key", sa.String(64), primary_key=True),
    sa.Column("expectation_id", sa.String(80), primary_key=True),
    sa.Column("revision", sa.Integer, primary_key=True),
    sa.Column("snapshot_id", sa.String(80), sa.ForeignKey("snapshots.id"), nullable=False),
    sa.Column("decided_by", sa.String(80), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("doc", JSONB, nullable=False),
)
verified_regression_memory = sa.Table(
    "verified_regression_memory",
    metadata,
    sa.Column("patch_id", sa.String(80), sa.ForeignKey("patch_candidates.id"), primary_key=True),
    sa.Column("snapshot_id", sa.String(80), sa.ForeignKey("snapshots.id"), nullable=False),
    sa.Column(
        "verification_id", sa.String(80), sa.ForeignKey("verification_results.id"), nullable=False
    ),
    sa.Column("ref_key", sa.String(64), nullable=False, index=True),
    sa.Column("doc", JSONB, nullable=False),
)


def _key(ref: SnapshotRef) -> str:
    return hashlib.sha256(ref.model_dump_json().encode()).hexdigest()


def _conflict(message: str) -> Exception:
    from code_intelligence.memory import MemoryConflict

    return MemoryConflict(message)


class PostgresMemoryStore:
    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or get_engine()

    def _validate(self, conn: sa.Connection, ref: SnapshotRef) -> None:
        ready = conn.execute(
            sa.select(index_snapshots.c.snapshot_id)
            .join(
                repositories,
                repositories.c.id == index_snapshots.c.repo_id,
            )
            .where(
                index_snapshots.c.project_id == ref.project_id,
                repositories.c.project_id == ref.project_id,
                index_snapshots.c.repo_id == ref.repo_id,
                index_snapshots.c.commit_sha == ref.commit_sha,
                index_snapshots.c.index_version == ref.index_version,
                index_snapshots.c.snapshot_id == ref.snapshot_id,
            )
        ).scalar()
        if ready is None:
            raise PermissionError("Exact project/repository snapshot is not ready")

    def put_decision(self, decision: ExpectationDecision) -> ExpectationDecision:
        from code_intelligence.memory import same_decision

        decision = ExpectationDecision.model_validate(decision.model_dump())
        key = _key(decision.snapshot_ref)
        lock = int.from_bytes(
            hashlib.sha256((key + decision.expectation_id).encode()).digest()[:8],
            "big",
            signed=True,
        )
        with self.engine.begin() as conn:
            self._validate(conn, decision.snapshot_ref)
            org_id = conn.execute(
                sa.select(projects.c.org_id).where(
                    projects.c.id == decision.snapshot_ref.project_id
                )
            ).scalar_one()
            if org_role(conn, decision.decided_by, org_id) not in {
                MemberRole.member,
                MemberRole.owner,
            }:
                raise PermissionError("Human decision requires project membership")
            conn.execute(sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
            doc = conn.execute(
                sa.select(expectation_decisions.c.doc)
                .where(
                    expectation_decisions.c.ref_key == key,
                    expectation_decisions.c.expectation_id == decision.expectation_id,
                )
                .order_by(expectation_decisions.c.revision.desc())
                .limit(1)
            ).scalar()
            previous = ExpectationDecision.model_validate(doc) if doc else None
            if previous and same_decision(previous, decision):
                return previous
            if (previous.revision if previous else 0) != decision.expected_revision:
                raise _conflict("CONFLICT_STATE: expectation decision revision changed")
            conn.execute(
                sa.insert(expectation_decisions).values(
                    ref_key=key,
                    expectation_id=decision.expectation_id,
                    revision=decision.revision,
                    snapshot_id=decision.snapshot_ref.snapshot_id,
                    decided_by=decision.decided_by,
                    doc=decision.model_dump(mode="json"),
                )
            )
            org_id = conn.execute(
                sa.select(projects.c.org_id).where(
                    projects.c.id == decision.snapshot_ref.project_id
                )
            ).scalar_one()
            audit.record(
                conn,
                org_id=org_id,
                project_id=decision.snapshot_ref.project_id,
                actor_type=ActorType.user,
                actor_id=decision.decided_by,
                action="expectation.decided",
                subject_type="expectation",
                subject_id=decision.expectation_id,
                details={
                    "snapshot_id": decision.snapshot_ref.snapshot_id,
                    "revision": decision.revision,
                    "status": decision.status,
                },
            )
        return decision

    def decisions(self, ref: SnapshotRef) -> list[ExpectationDecision]:
        with self.engine.begin() as conn:
            self._validate(conn, ref)
            latest = (
                sa.select(
                    expectation_decisions.c.doc,
                    expectation_decisions.c.expectation_id,
                    sa.func.row_number()
                    .over(
                        partition_by=expectation_decisions.c.expectation_id,
                        order_by=expectation_decisions.c.revision.desc(),
                    )
                    .label("position"),
                )
                .where(expectation_decisions.c.ref_key == _key(ref))
                .subquery()
            )
            query = (
                sa.select(latest.c.doc)
                .where(latest.c.position == 1)
                .order_by(latest.c.expectation_id)
            )
            docs = conn.execute(query).scalars().all()
        return [ExpectationDecision.model_validate(doc) for doc in docs]

    def history(
        self, ref: SnapshotRef, expectation_id: str, *, after: int = 0, limit: int = 100
    ) -> list[ExpectationDecision]:
        if after < 0 or not 1 <= limit <= 500:
            raise ValueError("Invalid decision pagination")
        with self.engine.begin() as conn:
            self._validate(conn, ref)
            docs = (
                conn.execute(
                    sa.select(expectation_decisions.c.doc)
                    .where(
                        expectation_decisions.c.ref_key == _key(ref),
                        expectation_decisions.c.expectation_id == expectation_id,
                        expectation_decisions.c.revision > after,
                    )
                    .order_by(expectation_decisions.c.revision)
                    .limit(limit)
                )
                .scalars()
                .all()
            )
        return [ExpectationDecision.model_validate(doc) for doc in docs]

    def put_regression(self, record: VerifiedRegression) -> None:
        record = VerifiedRegression.model_validate(record.model_dump())
        with self.engine.begin() as conn:
            self._validate(conn, record.snapshot_ref)
            conn.execute(
                pg_insert(verified_regression_memory)
                .values(
                    patch_id=record.patch_id,
                    snapshot_id=record.snapshot_ref.snapshot_id,
                    verification_id=record.verification_id,
                    ref_key=_key(record.snapshot_ref),
                    doc=record.model_dump(mode="json"),
                )
                .on_conflict_do_nothing()
            )
            doc = conn.execute(
                sa.select(verified_regression_memory.c.doc).where(
                    verified_regression_memory.c.patch_id == record.patch_id,
                )
            ).scalar_one()
            previous = VerifiedRegression.model_validate(doc)
            if previous.model_dump(exclude={"created_at"}) != record.model_dump(
                exclude={"created_at"}
            ):
                raise _conflict("CONFLICT_STATE: regression evidence is immutable")

    def regressions(self, ref: SnapshotRef) -> list[VerifiedRegression]:
        with self.engine.begin() as conn:
            self._validate(conn, ref)
            docs = (
                conn.execute(
                    sa.select(verified_regression_memory.c.doc)
                    .where(
                        verified_regression_memory.c.ref_key == _key(ref),
                    )
                    .order_by(verified_regression_memory.c.patch_id)
                )
                .scalars()
                .all()
            )
        return [VerifiedRegression.model_validate(doc) for doc in docs]


def build_memory_store() -> PostgresMemoryStore:
    return PostgresMemoryStore()
