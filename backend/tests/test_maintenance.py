"""Storage maintenance: bounded retention, ops endpoint, and the storage report.

Runs against the real test PostgreSQL — retention deletes are exercised end-to-end,
including RLS-scoped index_payloads/index_snapshots pruning.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import sqlalchemy as sa
from helpers import setup_project
from sqlalchemy.engine import Connection

from backend import jobs, maintenance
from backend.db import (
    agent_runs,
    assessment_events,
    assessments,
    findings,
    idempotency_keys,
    index_payloads,
    index_snapshots,
    monitoring_events,
    patch_candidates,
    reassessment_requests,
    runtime_windows,
    sessions,
    snapshots,
    transaction,
    verification_results,
    webhook_deliveries,
)
from backend.host import AssessmentHost
from backend.intel_store import PostgresPayloadStore, lock_ready_snapshot
from backend.intelligence import snapshot_ref
from backend.intelligence_memory import (
    PostgresMemoryStore,
    _key,
    expectation_decisions,
    verified_regression_memory,
)
from backend.settings import Settings, get_settings
from shared.base import utcnow
from shared.evidence import EvidenceRef
from shared.ids import IdPrefix, new_id
from shared.intelligence import SnapshotRef, SnapshotStats
from shared.intelligence_memory import ExpectationDecision, VerifiedRegression

OLD = datetime.now(UTC) - timedelta(days=400)


def _settings(**overrides: Any) -> Settings:
    # Tests exercise real deletes; production defaults to dry-run until an operator flips it.
    overrides.setdefault("retention_dry_run", False)
    return get_settings().model_copy(update=overrides)


def _ids(client_factory) -> dict[str, str]:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    ids["alice_uid"] = alice.me["user"]["id"]
    return ids


def _ready_payloads(ids: dict[str, str], sha: str) -> SnapshotRef:
    """A ready index snapshot with two payloads, via the real store path."""
    ref = SnapshotRef(
        project_id=ids["project"],
        repo_id=ids["repo"],
        commit_sha=sha,
        snapshot_id=new_id(IdPrefix.snp),
        index_version="intel-0.1",
    )
    store = PostgresPayloadStore()
    store.put_payload(ref, "intelligence_index", "index.json", b'{"symbols":[]}')
    store.put_payload(ref, "files", "app/main.py", b"{}")
    store.mark_ready(ref, SnapshotStats(files=1, symbols=0))
    return ref


def _age_scoped(table: sa.Table, project_id: str, where: Any, when: datetime = OLD) -> None:
    with transaction() as conn:
        maintenance._scope_tenant(conn, project_id)
        conn.execute(sa.update(table).where(where).values(created_at=when))


def _insert_assessment_reference(
    ids: dict[str, str], ref: SnapshotRef, *, state: str = "COMPLETED"
) -> str:
    assessment_id = new_id(IdPrefix.asm)
    with transaction() as conn:
        maintenance._scope_tenant(conn, ids["project"])
        conn.execute(
            sa.insert(assessments).values(
                id=assessment_id,
                project_id=ids["project"],
                repo_id=ids["repo"],
                scope_id=ids["scope"],
                commit_sha=ref.commit_sha,
                trigger="api",
                state=state,
                doc={"snapshot_id": ref.snapshot_id},
            )
        )
    return assessment_id


def _decision_for_ref(
    ids: dict[str, str], ref: SnapshotRef, expectation_id: str
) -> ExpectationDecision:
    return ExpectationDecision(
        snapshot_ref=ref,
        expectation_id=expectation_id,
        status="confirmed",
        reason="Retention race fixture decision",
        expected_revision=0,
        revision=1,
        decided_by=ids["alice_uid"],
        decided_at=utcnow(),
    )


def _index_snapshot_lock_waiting(timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with transaction() as conn:
            blocked = bool(
                conn.execute(
                    sa.text(
                        "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                        "WHERE wait_event_type = 'Lock' AND query LIKE '%index_snapshots%')"
                    )
                ).scalar_one()
            )
        if blocked:
            return True
        time.sleep(0.02)
    return False


def test_expired_sessions_and_idempotency_pruned(client_factory) -> None:
    ids = _ids(client_factory)
    with transaction() as conn:
        conn.execute(
            sa.insert(sessions).values(
                token_hash="dead" * 16,
                user_id=ids["alice_uid"],
                csrf_token="x" * 64,
                expires_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
        conn.execute(
            sa.insert(sessions).values(
                token_hash="live" * 16,
                user_id=ids["alice_uid"],
                csrf_token="y" * 64,
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
        for key, when in (("old", OLD), ("new", datetime.now(UTC))):
            conn.execute(
                sa.insert(idempotency_keys).values(
                    user_id=ids["alice_uid"],
                    key=key,
                    request_hash="h" * 64,
                    response_status=200,
                    response_body={},
                    created_at=when,
                )
            )
    out = maintenance.run_retention(s=_settings())
    assert out["deleted"]["expired_sessions"] == 1
    assert out["deleted"]["idempotency_keys"] == 1
    with transaction() as conn:
        # No expired session survives; live ones are untouched.
        assert (
            conn.execute(
                sa.select(sa.func.count())
                .select_from(sessions)
                .where(sessions.c.expires_at < sa.func.now())
            ).scalar_one()
            == 0
        )
        assert (
            conn.execute(
                sa.select(sa.func.count())
                .select_from(sessions)
                .where(sessions.c.token_hash == "live" * 16)
            ).scalar_one()
            == 1
        )
        assert (
            conn.execute(sa.select(sa.func.count()).select_from(idempotency_keys)).scalar_one() == 1
        )


def test_terminal_jobs_pruned_active_untouched(client_factory) -> None:
    _ids(client_factory)
    with transaction() as conn:
        for status, when in (
            ("succeeded", OLD),  # pruned
            ("failed", OLD),  # pruned
            ("dead", OLD),  # pruned
            ("succeeded", datetime.now(UTC)),  # fresh terminal: kept
            ("queued", OLD),  # old but non-terminal: kept
        ):
            jid, _ = jobs.enqueue(conn, "index_snapshot", {"n": 1})
            conn.execute(
                sa.update(jobs.jobs)
                .where(jobs.jobs.c.id == jid)
                .values(status=status, updated_at=when)
            )
    out = maintenance.run_retention(s=_settings())
    assert out["deleted"]["terminal_jobs"] == 3
    with transaction() as conn:
        left = dict(
            conn.execute(
                sa.select(jobs.jobs.c.status, sa.func.count()).group_by(jobs.jobs.c.status)
            ).all()
        )
    assert left == {"succeeded": 1, "queued": 1}


def test_history_tables_pruned(client_factory) -> None:
    ids = _ids(client_factory)
    with transaction() as conn:
        for when in (OLD, datetime.now(UTC)):
            conn.execute(
                sa.insert(webhook_deliveries).values(
                    delivery_id=new_id(IdPrefix.evt) + str(when.timestamp()),
                    source="github",
                    event_name="push",
                    payload_sha256="a" * 64,
                    received_at=when,
                )
            )
            conn.execute(
                sa.insert(monitoring_events).values(
                    id=new_id(IdPrefix.evt),
                    project_id=ids["project"],
                    repo_id=ids["repo"],
                    dedupe_key=new_id(IdPrefix.evt),
                    status="processed",
                    doc={},
                    created_at=when,
                )
            )
            conn.execute(
                sa.insert(reassessment_requests).values(
                    id=new_id(IdPrefix.evt),
                    project_id=ids["project"],
                    repo_id=ids["repo"],
                    status="skipped",
                    doc={},
                    created_at=when,
                )
            )
            conn.execute(
                sa.insert(runtime_windows).values(
                    id=new_id(IdPrefix.evt),
                    project_id=ids["project"],
                    source="api",
                    route="/x" + str(when.timestamp()),
                    window_start=when - timedelta(minutes=5),
                    window_end=when,
                    counters={},
                    score={},
                    created_at=when,
                )
            )
    out = maintenance.run_retention(s=_settings())
    assert out["deleted"]["webhook_deliveries"] == 1
    assert out["deleted"]["monitoring_events"] == 1
    assert out["deleted"]["reassessment_requests"] == 1
    assert out["deleted"]["runtime_windows"] == 1


def test_orphan_payloads_pruned_ready_untouched(client_factory) -> None:
    ids = _ids(client_factory)
    store = PostgresPayloadStore()
    # Orphan: payloads written, never mark_ready'd, aged past the orphan grace.
    orphan = SnapshotRef(
        project_id=ids["project"],
        repo_id=ids["repo"],
        commit_sha="a" * 40,
        snapshot_id=new_id(IdPrefix.snp),
        index_version="intel-0.1",
    )
    store.put_payload(orphan, "intelligence_index", "index.json", b"orphan")
    _age_scoped(index_payloads, ids["project"], index_payloads.c.snapshot_id == orphan.snapshot_id)
    # Ready: normal snapshot must survive.
    ready = _ready_payloads(ids, "b" * 40)
    out = maintenance.run_retention(s=_settings(retention_orphan_grace_hours=24))
    per_project = out["deleted"]["index_payloads"][ids["project"]]
    assert per_project["payload_rows"] == 1
    assert per_project["orphan_snapshots"] == 1
    with transaction() as conn:
        maintenance._scope_tenant(conn, ids["project"])
        survivors = set(conn.execute(sa.select(index_payloads.c.snapshot_id)).scalars())
    assert survivors == {ready.snapshot_id}
    # Ready snapshot still resolves.
    assert store.find_snapshot(ids["project"], ids["repo"], "b" * 40, "intel-0.1") is not None


def test_superseded_ready_snapshots_pruned_with_audit(client_factory) -> None:
    ids = _ids(client_factory)
    store = PostgresPayloadStore()
    refs = [_ready_payloads(ids, f"{i:040x}") for i in range(8)]
    # Stagger created_at (all past the grace window) so "newest N kept" is deterministic.
    _age_scoped(index_payloads, ids["project"], sa.true())
    for i, ref in enumerate(refs):
        _age_scoped(
            index_snapshots,
            ids["project"],
            index_snapshots.c.snapshot_id == ref.snapshot_id,
            when=OLD + timedelta(minutes=i),
        )
    s = _settings(retention_snapshots_per_repo=5, retention_snapshot_grace_days=7)
    out = maintenance.run_retention(s=s)
    per_project = out["deleted"]["index_payloads"][ids["project"]]
    assert per_project["superseded_snapshots"] == 3
    assert per_project["payload_rows"] == 6  # 2 payloads per snapshot
    with transaction() as conn:
        maintenance._scope_tenant(conn, ids["project"])
        left = conn.execute(sa.select(index_snapshots.c.snapshot_id)).scalars().all()
    assert sorted(left) == sorted(r.snapshot_id for r in refs[3:])  # newest 5 kept
    # Pruned snapshots no longer resolve.
    with pytest.raises(KeyError):
        store.find_snapshot(ids["project"], ids["repo"], refs[0].commit_sha, "intel-0.1")
    # An audit row was appended for the prune.
    with transaction() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT doc->>'action' FROM audit_events WHERE doc->>'action' = 'maintenance.retention'"
            )
        ).all()
    assert rows


def test_active_assessment_protects_snapshot(client_factory) -> None:
    ids = _ids(client_factory)
    refs = [_ready_payloads(ids, f"{i:040x}") for i in range(7)]
    _age_scoped(index_payloads, ids["project"], sa.true())
    for i, ref in enumerate(refs):
        _age_scoped(
            index_snapshots,
            ids["project"],
            index_snapshots.c.snapshot_id == ref.snapshot_id,
            when=OLD + timedelta(minutes=i),
        )
    protected = refs[0].snapshot_id  # oldest → always a prune candidate unless protected
    with transaction() as conn:
        conn.execute(
            sa.insert(assessments).values(
                id=new_id(IdPrefix.asm),
                project_id=ids["project"],
                repo_id=ids["repo"],
                scope_id=ids["scope"],
                commit_sha=refs[0].commit_sha,
                trigger="api",
                state="CREATED",
                doc={"snapshot_id": protected},
            )
        )
    s = _settings(retention_snapshots_per_repo=1, retention_snapshot_grace_days=7)
    out = maintenance.run_retention(s=s)
    per_project = out["deleted"]["index_payloads"][ids["project"]]
    assert per_project["superseded_snapshots"] == 5  # 7 - 1 keep - 1 protected
    with transaction() as conn:
        maintenance._scope_tenant(conn, ids["project"])
        left = set(conn.execute(sa.select(index_snapshots.c.snapshot_id)).scalars())
    assert protected in left


def test_retention_preserves_customer_references_and_allows_old_assessment_expiry(
    client_factory,
) -> None:
    ids = _ids(client_factory)
    refs = [_ready_payloads(ids, f"{i:040x}") for i in range(9)]
    _age_scoped(index_payloads, ids["project"], sa.true())
    for i, ref in enumerate(refs):
        _age_scoped(
            index_snapshots,
            ids["project"],
            index_snapshots.c.snapshot_id == ref.snapshot_id,
            when=OLD + timedelta(minutes=i),
        )
    assessment_ids = [new_id(IdPrefix.asm) for _ in refs]
    finding_id, patch_id, verification_id = (
        new_id(IdPrefix.fnd),
        new_id(IdPrefix.pat),
        new_id(IdPrefix.ver),
    )
    with transaction() as conn:
        for i, ref in enumerate(refs):
            conn.execute(
                sa.insert(assessments).values(
                    id=assessment_ids[i],
                    project_id=ids["project"],
                    repo_id=ids["repo"],
                    scope_id=ids["scope"],
                    commit_sha=ref.commit_sha,
                    trigger="api",
                    state="COMPLETED" if i == 3 else ("CREATED" if i == 4 else "COMPLETED"),
                    doc={"snapshot_id": ref.snapshot_id} if i in {3, 4} else {},
                )
            )
        conn.execute(
            sa.insert(findings).values(
                id=finding_id,
                project_id=ids["project"],
                assessment_id=assessment_ids[0],
                kind="vulnerability",
                status="resolved",
                paths=[],
                doc={"snapshot_id": refs[0].snapshot_id},
            )
        )
        conn.execute(sa.insert(patch_candidates).values(id=patch_id, finding_id=finding_id, doc={}))
        conn.execute(
            sa.insert(verification_results).values(
                id=verification_id, patch_id=patch_id, verdict="accepted", doc={}
            )
        )
        regression = VerifiedRegression(
            snapshot_ref=refs[1],
            finding_id=finding_id,
            patch_id=patch_id,
            verification_id=verification_id,
            affected_paths=["app/main.py"],
            test_paths=["tests/test_main.py"],
            evidence=[
                EvidenceRef(
                    kind="test_run",
                    artifact_id=new_id(IdPrefix.art),
                    sha256="a" * 64,
                    commit_sha=refs[1].commit_sha,
                    provenance="retention fixture",
                )
            ],
            created_at=utcnow(),
        )
        conn.execute(
            sa.insert(verified_regression_memory).values(
                patch_id=patch_id,
                snapshot_id=refs[1].snapshot_id,
                verification_id=verification_id,
                ref_key=_key(refs[1]),
                doc=regression.model_dump(mode="json"),
            )
        )
        decision = ExpectationDecision(
            snapshot_ref=refs[2],
            expectation_id="exp_fixture0000",
            status="confirmed",
            reason="Owner confirmed this expectation",
            expected_revision=0,
            revision=1,
            decided_by=ids["alice_uid"],
            decided_at=utcnow(),
        )
        conn.execute(
            sa.insert(expectation_decisions).values(
                ref_key=_key(refs[2]),
                expectation_id=decision.expectation_id,
                revision=1,
                snapshot_id=refs[2].snapshot_id,
                decided_by=ids["alice_uid"],
                doc=decision.model_dump(mode="json"),
            )
        )
    s = _settings(retention_snapshots_per_repo=1)
    out = maintenance.run_retention(s=s)
    report = out["deleted"]["index_payloads"][ids["project"]]
    assert report["superseded_snapshots"] == 3
    assert report["protected_snapshots"]["a_findings"] == 1
    assert report["protected_snapshots"]["b_verified_regression_memory"] == 1
    assert report["protected_snapshots"]["c_expectation_decisions"] == 1
    assert report["protected_snapshots"]["d_non_terminal_assessments"] == 1
    assert report["protected_snapshots"]["f_all_assessments"] == 2
    assert PostgresMemoryStore().regressions(refs[1])
    assert PostgresMemoryStore().decisions(refs[2])
    for ref in refs[:5]:
        assert snapshot_ref(ref.snapshot_id) == ref
    assert PostgresPayloadStore().get_payload(refs[0], "intelligence_index", "index.json")


def test_terminal_assessment_snapshot_expires_only_after_configured_age(client_factory) -> None:
    ids = _ids(client_factory)
    refs = [_ready_payloads(ids, f"{i:040x}") for i in range(8)]
    for i, ref in enumerate(refs):
        _age_scoped(
            index_snapshots,
            ids["project"],
            index_snapshots.c.snapshot_id == ref.snapshot_id,
            when=OLD + timedelta(minutes=i),
        )
    for ref in refs[6:]:
        _age_scoped(
            index_snapshots,
            ids["project"],
            index_snapshots.c.snapshot_id == ref.snapshot_id,
            when=datetime.now(UTC),
        )
    terminal_ids = [new_id(IdPrefix.asm) for _ in range(4)]
    finding_id = new_id(IdPrefix.fnd)
    patch_id = new_id(IdPrefix.pat)
    verification_id = new_id(IdPrefix.ver)
    with transaction() as conn:
        for i in range(4):
            conn.execute(
                sa.insert(assessments).values(
                    id=terminal_ids[i],
                    project_id=ids["project"],
                    repo_id=ids["repo"],
                    scope_id=ids["scope"],
                    commit_sha=refs[i].commit_sha,
                    trigger="api",
                    state="COMPLETED" if i != 3 else "COMPLETED",
                    doc={"snapshot_id": refs[i].snapshot_id},
                )
            )
        conn.execute(
            sa.insert(findings).values(
                id=finding_id,
                project_id=ids["project"],
                assessment_id=terminal_ids[0],
                kind="vulnerability",
                status="resolved",
                paths=[],
                doc={"snapshot_id": refs[0].snapshot_id},
            )
        )
        conn.execute(sa.insert(patch_candidates).values(id=patch_id, finding_id=finding_id, doc={}))
        conn.execute(
            sa.insert(verification_results).values(
                id=verification_id, patch_id=patch_id, verdict="accepted", doc={}
            )
        )
        conn.execute(
            sa.insert(verified_regression_memory).values(
                patch_id=patch_id,
                snapshot_id=refs[1].snapshot_id,
                verification_id=verification_id,
                ref_key="d" * 64,
                doc={},
            )
        )
        conn.execute(
            sa.insert(expectation_decisions).values(
                ref_key="e" * 64,
                expectation_id="exp_fixture0000",
                revision=1,
                snapshot_id=refs[2].snapshot_id,
                decided_by=ids["alice_uid"],
                doc={},
            )
        )
        active_id = new_id(IdPrefix.asm)
        conn.execute(
            sa.insert(assessments).values(
                id=active_id,
                project_id=ids["project"],
                repo_id=ids["repo"],
                scope_id=ids["scope"],
                commit_sha=refs[4].commit_sha,
                trigger="api",
                state="CREATED",
                doc={"snapshot_id": refs[4].snapshot_id},
            )
        )
    settings = _settings(
        retention_snapshots_per_repo=1,
        retention_protect_assessment_snapshots=False,
        retention_assessment_snapshot_days=30,
    )
    _age_scoped(
        index_snapshots,
        ids["project"],
        index_snapshots.c.snapshot_id == refs[3].snapshot_id,
        when=datetime.now(UTC) - timedelta(days=29),
    )
    maintenance.run_retention(s=settings)
    with transaction() as conn:
        maintenance._scope_tenant(conn, ids["project"])
        assert conn.execute(
            sa.select(index_snapshots.c.snapshot_id).where(
                index_snapshots.c.snapshot_id == refs[3].snapshot_id
            )
        ).first()
    _age_scoped(
        index_snapshots,
        ids["project"],
        index_snapshots.c.snapshot_id == refs[3].snapshot_id,
        when=datetime.now(UTC) - timedelta(days=31),
    )
    maintenance.run_retention(s=settings)
    with transaction() as conn:
        maintenance._scope_tenant(conn, ids["project"])
        left = set(conn.execute(sa.select(index_snapshots.c.snapshot_id)).scalars())
    assert refs[3].snapshot_id not in left
    assert {ref.snapshot_id for ref in refs[:3] + refs[4:5]} <= left


def test_scale_retention_preserves_46_memory_487_findings_and_614_assessments(
    client_factory,
) -> None:
    ids = _ids(client_factory)
    refs = [
        SnapshotRef(
            project_id=ids["project"],
            repo_id=ids["repo"],
            commit_sha=f"{i:040x}",
            snapshot_id=new_id(IdPrefix.snp),
            index_version="intel-0.1",
        )
        for i in range(279)
    ]
    assessment_only_refs = [
        SnapshotRef(
            project_id=ids["project"],
            repo_id=ids["repo"],
            commit_sha=f"{i + 279:040x}",
            snapshot_id=new_id(IdPrefix.snp),
            index_version="intel-0.1",
        )
        for i in range(10)
    ]
    sentinel = SnapshotRef(
        project_id=ids["project"],
        repo_id=ids["repo"],
        commit_sha=f"{289:040x}",
        snapshot_id=new_id(IdPrefix.snp),
        index_version="intel-0.1",
    )
    all_refs = refs + assessment_only_refs + [sentinel]
    assessments_rows = []
    for i in range(614):
        ref = refs[i % len(refs)] if i < 604 else assessment_only_refs[i - 604]
        assessments_rows.append(
            {
                "id": new_id(IdPrefix.asm),
                "project_id": ids["project"],
                "repo_id": ids["repo"],
                "scope_id": ids["scope"],
                "commit_sha": ref.commit_sha,
                "trigger": "api",
                "state": "COMPLETED",
                "doc": {"snapshot_id": ref.snapshot_id},
            }
        )
    finding_rows = [
        {
            "id": new_id(IdPrefix.fnd),
            "project_id": ids["project"],
            "assessment_id": assessments_rows[i]["id"],
            "kind": "vulnerability",
            "status": "resolved",
            "paths": [],
            "doc": {"snapshot_id": refs[i % len(refs)].snapshot_id},
        }
        for i in range(487)
    ]
    patches = [
        {"id": new_id(IdPrefix.pat), "finding_id": finding_rows[i]["id"], "doc": {}}
        for i in range(46)
    ]
    verifications = [
        {
            "id": new_id(IdPrefix.ver),
            "patch_id": patches[i]["id"],
            "verdict": "accepted",
            "doc": {},
        }
        for i in range(46)
    ]
    regression_records = [
        VerifiedRegression(
            snapshot_ref=refs[i],
            finding_id=finding_rows[i]["id"],
            patch_id=patches[i]["id"],
            verification_id=verifications[i]["id"],
            affected_paths=["app/main.py"],
            test_paths=["tests/test_main.py"],
            evidence=[
                EvidenceRef(
                    kind="test_run",
                    artifact_id=new_id(IdPrefix.art),
                    sha256=f"{i + 1:064x}",
                    commit_sha=refs[i].commit_sha,
                    provenance="retention scale fixture",
                )
            ],
            created_at=utcnow(),
        )
        for i in range(46)
    ]
    regressions = [
        {
            "patch_id": patches[i]["id"],
            "snapshot_id": refs[i].snapshot_id,
            "verification_id": verifications[i]["id"],
            "ref_key": _key(refs[i]),
            "doc": regression_records[i].model_dump(mode="json"),
        }
        for i in range(46)
    ]
    decision_ref = refs[46]
    decision = ExpectationDecision(
        snapshot_ref=decision_ref,
        expectation_id="exp_scale_fixture",
        status="confirmed",
        reason="Scale fixture decision",
        expected_revision=0,
        revision=1,
        decided_by=ids["alice_uid"],
        decided_at=utcnow(),
    )
    payload_rows = []
    snapshot_rows = []
    metadata_rows = []
    now = datetime.now(UTC)
    for ref in all_refs:
        data = b'{"symbols":[]}'
        metadata_rows.append(
            {
                "id": ref.snapshot_id,
                "repo_id": ref.repo_id,
                "commit_sha": ref.commit_sha,
                "index_version": ref.index_version,
                "status": "ready",
                "doc": {
                    "id": ref.snapshot_id,
                    "repo_id": ref.repo_id,
                    "commit_sha": ref.commit_sha,
                    "status": "ready",
                    "index_version": ref.index_version,
                    "stats": {"files": 1},
                    "created_at": OLD.isoformat(),
                    "completed_at": OLD.isoformat(),
                },
                "created_at": now if ref == sentinel else OLD,
            }
        )
        snapshot_rows.append(
            {
                "project_id": ref.project_id,
                "repo_id": ref.repo_id,
                "commit_sha": ref.commit_sha,
                "index_version": ref.index_version,
                "snapshot_id": ref.snapshot_id,
                "stats": {},
                "created_at": now if ref == sentinel else OLD,
            }
        )
        payload_rows.append(
            {
                "project_id": ref.project_id,
                "repo_id": ref.repo_id,
                "commit_sha": ref.commit_sha,
                "index_version": ref.index_version,
                "kind": "intelligence_index",
                "key": "index.json",
                "snapshot_id": ref.snapshot_id,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
                "data": data,
                "created_at": now if ref == sentinel else OLD,
            }
        )
    with transaction() as conn:
        maintenance._scope_tenant(conn, ids["project"])
        conn.execute(sa.insert(assessments), assessments_rows)
        conn.execute(sa.insert(findings), finding_rows)
        conn.execute(sa.insert(patch_candidates), patches)
        conn.execute(sa.insert(verification_results), verifications)
        conn.execute(sa.insert(snapshots), metadata_rows)
        conn.execute(sa.insert(verified_regression_memory), regressions)
        conn.execute(
            sa.insert(expectation_decisions).values(
                ref_key=_key(decision_ref),
                expectation_id=decision.expectation_id,
                revision=decision.revision,
                snapshot_id=decision_ref.snapshot_id,
                decided_by=ids["alice_uid"],
                doc=decision.model_dump(mode="json"),
            )
        )
        conn.execute(sa.insert(index_snapshots), snapshot_rows)
        conn.execute(sa.insert(index_payloads), payload_rows)
    out = maintenance.run_retention(s=_settings(retention_snapshots_per_repo=1))
    report = out["deleted"]["index_payloads"][ids["project"]]
    assert report["protected_snapshots"]["a_findings"] == 279
    assert report["protected_snapshots"]["b_verified_regression_memory"] == 46
    assert report["protected_snapshots"]["c_expectation_decisions"] == 1
    assert report["protected_snapshots"]["f_all_assessments"] == 289
    with transaction() as conn:
        maintenance._scope_tenant(conn, ids["project"])
        remaining = set(conn.execute(sa.select(index_snapshots.c.snapshot_id)).scalars())
    assert remaining == {ref.snapshot_id for ref in all_refs}
    store = PostgresPayloadStore()
    memory = PostgresMemoryStore()
    for i, ref in enumerate(refs[:46]):
        records = memory.regressions(ref)
        assert len(records) == 1 and records[0].patch_id == patches[i]["id"]
    assert memory.decisions(decision_ref)
    for ref in refs + assessment_only_refs:
        assert snapshot_ref(ref.snapshot_id) == ref
    for ref in refs[:10]:
        assert store.get_payload(ref, "intelligence_index", "index.json") == b'{"symbols":[]}'

    out = maintenance.run_retention(
        s=_settings(
            retention_snapshots_per_repo=1,
            retention_protect_assessment_snapshots=False,
            retention_assessment_snapshot_days=30,
        )
    )
    report = out["deleted"]["index_payloads"][ids["project"]]
    assert report["superseded_snapshots"] == len(assessment_only_refs)
    with transaction() as conn:
        maintenance._scope_tenant(conn, ids["project"])
        remaining = set(conn.execute(sa.select(index_snapshots.c.snapshot_id)).scalars())
    assert remaining == {ref.snapshot_id for ref in refs + [sentinel]}
    for i, ref in enumerate(refs[:46]):
        records = memory.regressions(ref)
        assert len(records) == 1 and records[0].patch_id == patches[i]["id"]
    assert memory.decisions(decision_ref)
    for ref in refs:
        assert snapshot_ref(ref.snapshot_id) == ref
    for ref in refs[:10]:
        assert store.get_payload(ref, "intelligence_index", "index.json") == b'{"symbols":[]}'


def test_binding_lock_serializes_with_cleanup(client_factory, monkeypatch) -> None:
    ids = _ids(client_factory)
    refs = [_ready_payloads(ids, f"{i:040x}") for i in range(2)]
    mismatched_ref = refs[0].model_copy(update={"snapshot_id": new_id(IdPrefix.snp)})
    with transaction() as conn:
        assert not lock_ready_snapshot(conn, mismatched_ref)
    for i, ref in enumerate(refs):
        _age_scoped(
            index_snapshots,
            ids["project"],
            index_snapshots.c.snapshot_id == ref.snapshot_id,
            when=OLD + timedelta(minutes=i),
        )
    original_scope = maintenance._scope_tenant

    def scoped_with_timeout(conn: Connection, project_id: str) -> None:
        original_scope(conn, project_id)
        conn.execute(sa.text("SET LOCAL lock_timeout = '3s'"))

    monkeypatch.setattr(maintenance, "_scope_tenant", scoped_with_timeout)
    locked = threading.Event()
    release_binding = threading.Event()
    cleanup_started = threading.Event()
    result: dict[str, object] = {}

    def bind() -> None:
        with transaction() as conn:
            assert lock_ready_snapshot(conn, refs[0])
            locked.set()
            assert release_binding.wait(5)
            conn.execute(
                sa.insert(assessments).values(
                    id=new_id(IdPrefix.asm),
                    project_id=ids["project"],
                    repo_id=ids["repo"],
                    scope_id=ids["scope"],
                    commit_sha=refs[0].commit_sha,
                    trigger="api",
                    state="CREATED",
                    doc={"snapshot_id": refs[0].snapshot_id},
                )
            )

    def cleanup() -> None:
        cleanup_started.set()
        result.update(
            maintenance.run_retention(s=_settings(retention_snapshots_per_repo=1), dry_run=False)
        )

    binder = threading.Thread(target=bind)
    binder.start()
    assert locked.wait(5)
    cleaner = threading.Thread(target=cleanup)
    cleaner.start()
    assert cleanup_started.wait(5)
    blocked = _index_snapshot_lock_waiting()
    assert blocked, "cleanup did not wait on the binding's FOR SHARE lock"
    release_binding.set()
    binder.join(5)
    cleaner.join(5)
    assert not binder.is_alive() and not cleaner.is_alive()
    per_project = result["deleted"]["index_payloads"][ids["project"]]
    assert per_project["skipped_now_protected"] == 1

    first, second = [_ready_payloads(ids, f"{i + 10:040x}") for i in range(2)]
    _age_scoped(
        index_snapshots,
        ids["project"],
        index_snapshots.c.snapshot_id == first.snapshot_id,
        when=OLD,
    )
    _age_scoped(
        index_snapshots,
        ids["project"],
        index_snapshots.c.snapshot_id == second.snapshot_id,
        when=datetime.now(UTC),
    )
    original_is_protected = maintenance._snapshot_is_protected
    cleanup_locked = threading.Event()
    release_cleanup = threading.Event()
    binding_started = threading.Event()
    cleanup_first_result: dict[str, object] = {}

    def pause_after_cleanup_lock(
        conn: Connection,
        project_id: str,
        snapshot_id: str,
        s: Settings,
        *,
        created_at: datetime,
        grace_cutoff: datetime,
        assessment_grace_cutoff: datetime,
    ) -> bool:
        if snapshot_id == first.snapshot_id:
            cleanup_locked.set()
            assert release_cleanup.wait(5)
        return original_is_protected(
            conn,
            project_id,
            snapshot_id,
            s,
            created_at=created_at,
            grace_cutoff=grace_cutoff,
            assessment_grace_cutoff=assessment_grace_cutoff,
        )

    monkeypatch.setattr(maintenance, "_snapshot_is_protected", pause_after_cleanup_lock)

    def cleanup_first() -> None:
        cleanup_first_result.update(
            maintenance.run_retention(s=_settings(retention_snapshots_per_repo=1), dry_run=False)
        )

    def bind_after_cleanup_lock() -> None:
        with transaction() as conn:
            conn.execute(sa.text("SET LOCAL lock_timeout = '3s'"))
            binding_started.set()
            cleanup_first_result["ready"] = lock_ready_snapshot(conn, first)

    cleaner = threading.Thread(target=cleanup_first)
    cleaner.start()
    assert cleanup_locked.wait(5)
    binder = threading.Thread(target=bind_after_cleanup_lock)
    binder.start()
    assert binding_started.wait(5)
    blocked = _index_snapshot_lock_waiting()
    assert blocked, "binding did not wait on cleanup's FOR UPDATE lock"
    release_cleanup.set()
    binder.join(5)
    cleaner.join(5)
    assert not binder.is_alive() and not cleaner.is_alive()
    assert cleanup_first_result["ready"] is False

    client = client_factory("alice")
    response = client.post(
        f"/api/v1/projects/{ids['project']}/assessments",
        json={
            "scope_id": ids["scope"],
            "repo_id": ids["repo"],
            "commit_sha": first.commit_sha,
            "snapshot_id": first.snapshot_id,
        },
    )
    assert response.status_code == 202, response.text
    assessment = response.json()["assessment"]
    assert assessment["snapshot_id"] is None
    assert AssessmentHost(assessment["id"]).attach_snapshot(first) is False


def test_terminal_assessment_uses_stricter_snapshot_and_assessment_grace(
    client_factory: Any,
) -> None:
    ids = _ids(client_factory)
    within_assessment_grace, beyond_both_graces, newest = [
        _ready_payloads(ids, f"{i + 80:040x}") for i in range(3)
    ]
    _age_scoped(
        index_snapshots,
        ids["project"],
        index_snapshots.c.snapshot_id == within_assessment_grace.snapshot_id,
        when=datetime.now(UTC) - timedelta(days=31),
    )
    _age_scoped(
        index_snapshots,
        ids["project"],
        index_snapshots.c.snapshot_id == beyond_both_graces.snapshot_id,
        when=datetime.now(UTC) - timedelta(days=46),
    )
    _insert_assessment_reference(ids, within_assessment_grace)
    _insert_assessment_reference(ids, beyond_both_graces)

    out = maintenance.run_retention(
        s=_settings(
            retention_snapshots_per_repo=1,
            retention_snapshot_grace_days=45,
            retention_assessment_snapshot_days=30,
            retention_protect_assessment_snapshots=False,
        ),
        dry_run=False,
    )

    report = out["deleted"]["index_payloads"][ids["project"]]
    assert report["superseded_snapshots"] == 1
    with transaction() as conn:
        maintenance._scope_tenant(conn, ids["project"])
        remaining = set(conn.execute(sa.select(index_snapshots.c.snapshot_id)).scalars())
    assert within_assessment_grace.snapshot_id in remaining
    assert beyond_both_graces.snapshot_id not in remaining
    assert newest.snapshot_id in remaining


def test_delete_recheck_applies_assessment_age_after_new_reference(
    client_factory: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _ids(client_factory)
    target, newest = [_ready_payloads(ids, f"{i + 90:040x}") for i in range(2)]
    _age_scoped(
        index_snapshots,
        ids["project"],
        index_snapshots.c.snapshot_id == target.snapshot_id,
        when=datetime.now(UTC) - timedelta(days=10),
    )
    original = maintenance._snapshot_is_protected
    inserted = False

    def add_assessment_before_recheck(
        conn: Connection,
        project_id: str,
        snapshot_id: str,
        s: Settings,
        *,
        created_at: datetime,
        grace_cutoff: datetime,
        assessment_grace_cutoff: datetime,
    ) -> bool:
        nonlocal inserted
        if snapshot_id == target.snapshot_id and not inserted:
            inserted = True
            _insert_assessment_reference(ids, target)
        return original(
            conn,
            project_id,
            snapshot_id,
            s,
            created_at=created_at,
            grace_cutoff=grace_cutoff,
            assessment_grace_cutoff=assessment_grace_cutoff,
        )

    monkeypatch.setattr(maintenance, "_snapshot_is_protected", add_assessment_before_recheck)
    out = maintenance.run_retention(
        s=_settings(
            retention_snapshots_per_repo=1,
            retention_snapshot_grace_days=7,
            retention_assessment_snapshot_days=30,
            retention_protect_assessment_snapshots=False,
        ),
        dry_run=False,
    )

    report = out["deleted"]["index_payloads"][ids["project"]]
    assert inserted
    assert report["skipped_now_protected"] == 1
    with transaction() as conn:
        maintenance._scope_tenant(conn, ids["project"])
        remaining = set(conn.execute(sa.select(index_snapshots.c.snapshot_id)).scalars())
    assert target.snapshot_id in remaining
    assert newest.snapshot_id in remaining


def test_decision_write_waits_for_cleanup_delete(
    client_factory: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _ids(client_factory)
    target, newest = [_ready_payloads(ids, f"{i + 100:040x}") for i in range(2)]
    _age_scoped(
        index_snapshots,
        ids["project"],
        index_snapshots.c.snapshot_id == target.snapshot_id,
        when=OLD,
    )
    decision = _decision_for_ref(ids, target, "exp_cleanupfirst01")
    store = PostgresMemoryStore()
    original = maintenance._snapshot_is_protected
    cleanup_locked = threading.Event()
    release_cleanup = threading.Event()
    writer_started = threading.Event()
    outcome: dict[str, object] = {}

    def pause_cleanup_with_lock(
        conn: Connection,
        project_id: str,
        snapshot_id: str,
        s: Settings,
        *,
        created_at: datetime,
        grace_cutoff: datetime,
        assessment_grace_cutoff: datetime,
    ) -> bool:
        if snapshot_id == target.snapshot_id:
            cleanup_locked.set()
            assert release_cleanup.wait(5)
        return original(
            conn,
            project_id,
            snapshot_id,
            s,
            created_at=created_at,
            grace_cutoff=grace_cutoff,
            assessment_grace_cutoff=assessment_grace_cutoff,
        )

    monkeypatch.setattr(maintenance, "_snapshot_is_protected", pause_cleanup_with_lock)

    def cleanup() -> None:
        outcome.update(
            maintenance.run_retention(s=_settings(retention_snapshots_per_repo=1), dry_run=False)
        )

    def write_decision() -> None:
        writer_started.set()
        try:
            store.put_decision(decision)
        except Exception as exc:
            outcome["write_error"] = exc

    cleaner = threading.Thread(target=cleanup)
    cleaner.start()
    assert cleanup_locked.wait(5)
    writer = threading.Thread(target=write_decision)
    writer.start()
    assert writer_started.wait(5)
    blocked = _index_snapshot_lock_waiting()
    release_cleanup.set()
    writer.join(5)
    cleaner.join(5)

    assert blocked, "put_decision did not wait for cleanup's FOR UPDATE lock"
    assert not writer.is_alive() and not cleaner.is_alive()
    assert isinstance(outcome.get("write_error"), PermissionError)
    with transaction() as conn:
        maintenance._scope_tenant(conn, ids["project"])
        remaining = set(conn.execute(sa.select(index_snapshots.c.snapshot_id)).scalars())
        decision_count = conn.execute(
            sa.select(sa.func.count()).where(
                expectation_decisions.c.snapshot_id == target.snapshot_id
            )
        ).scalar_one()
    assert decision_count == 0
    assert target.snapshot_id not in remaining
    assert newest.snapshot_id in remaining


def test_decision_write_before_cleanup_delete_is_rechecked(
    client_factory: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _ids(client_factory)
    target, newest = [_ready_payloads(ids, f"{i + 110:040x}") for i in range(2)]
    _age_scoped(
        index_snapshots,
        ids["project"],
        index_snapshots.c.snapshot_id == target.snapshot_id,
        when=OLD,
    )
    decision = _decision_for_ref(ids, target, "exp_writerfirst01")
    store = PostgresMemoryStore()
    original_targets = maintenance._payload_prune_targets
    plan_ready = threading.Event()
    decision_committed = threading.Event()
    outcome: dict[str, object] = {}

    def pause_after_plan(
        conn: Connection, project_id: str, s: Settings
    ) -> tuple[set[str], set[str]]:
        targets = original_targets(conn, project_id, s)
        if project_id == ids["project"] and target.snapshot_id in targets[1]:
            plan_ready.set()
            assert decision_committed.wait(5)
        return targets

    monkeypatch.setattr(maintenance, "_payload_prune_targets", pause_after_plan)

    def cleanup() -> None:
        outcome.update(
            maintenance.run_retention(s=_settings(retention_snapshots_per_repo=1), dry_run=False)
        )

    def write_decision() -> None:
        try:
            store.put_decision(decision)
        except Exception as exc:
            outcome["write_error"] = exc
        finally:
            decision_committed.set()

    cleaner = threading.Thread(target=cleanup)
    cleaner.start()
    assert plan_ready.wait(5)
    writer = threading.Thread(target=write_decision)
    writer.start()
    writer.join(5)
    assert not writer.is_alive()
    cleaner.join(5)

    assert not cleaner.is_alive()
    assert "write_error" not in outcome
    report = outcome["deleted"]["index_payloads"][ids["project"]]
    assert report["skipped_now_protected"] == 1
    with transaction() as conn:
        maintenance._scope_tenant(conn, ids["project"])
        remaining = set(conn.execute(sa.select(index_snapshots.c.snapshot_id)).scalars())
        decision_count = conn.execute(
            sa.select(sa.func.count()).where(
                expectation_decisions.c.snapshot_id == target.snapshot_id
            )
        ).scalar_one()
    assert target.snapshot_id in remaining
    assert newest.snapshot_id in remaining
    assert decision_count == 1


def test_ops_maintenance_requires_token_and_current_plan(client_factory, settings_override) -> None:
    client = client_factory()
    settings_override(OPS_API_TOKEN="test-ops-token", RETENTION_DRY_RUN="true")
    headers = {"Authorization": "Bearer test-ops-token"}
    default = client.post("/api/v1/ops/maintenance", headers=headers, json={})
    assert default.status_code == 200 and default.json()["dry_run"] is True
    assert default.json()["plan_digest"]
    dry_report = client.post("/api/v1/ops/maintenance/dry-run-report", headers=headers)
    assert dry_report.status_code == 200
    assert dry_report.json()["plan_digest"] and "snapshot_ids" in dry_report.json()
    refused = client.post("/api/v1/ops/maintenance", headers=headers, json={"dry_run": False})
    assert refused.status_code == 409
    assert refused.json()["detail"] == "retention dry-run is enforced"

    settings_override(
        OPS_API_TOKEN="test-ops-token",
        OPS_DESTRUCTIVE_TOKEN="",
        RETENTION_DRY_RUN="false",
    )
    no_token = client.post("/api/v1/ops/maintenance", headers=headers, json={"dry_run": False})
    assert no_token.status_code == 403
    assert no_token.json()["detail"] == "destructive maintenance disabled"
    settings_override(
        OPS_API_TOKEN="test-ops-token",
        OPS_DESTRUCTIVE_TOKEN="correct-secret",
        RETENTION_DRY_RUN="false",
    )
    wrong_token = client.post(
        "/api/v1/ops/maintenance",
        headers={**headers, "X-Ops-Destructive-Token": "wrong-secret"},
        json={"dry_run": False},
    )
    assert wrong_token.status_code == 403
    plan = client.post("/api/v1/ops/maintenance", headers=headers, json={}).json()
    authorized = {**headers, "X-Ops-Destructive-Token": "correct-secret"}
    wrong_digest = client.post(
        "/api/v1/ops/maintenance",
        headers=authorized,
        json={"dry_run": False, "confirm_plan_digest": "wrong"},
    )
    assert wrong_digest.status_code == 409
    assert wrong_digest.json()["detail"]["plan_digest"] == plan["plan_digest"]
    success = client.post(
        "/api/v1/ops/maintenance",
        headers=authorized,
        json={"dry_run": False, "confirm_plan_digest": plan["plan_digest"]},
    )
    assert success.status_code == 200, success.text
    assert success.json()["dry_run"] is False


def test_dry_run_deletes_nothing(client_factory) -> None:
    ids = _ids(client_factory)
    orphan = SnapshotRef(
        project_id=ids["project"],
        repo_id=ids["repo"],
        commit_sha="c" * 40,
        snapshot_id=new_id(IdPrefix.snp),
        index_version="intel-0.1",
    )
    PostgresPayloadStore().put_payload(orphan, "intelligence_index", "i.json", b"x")
    _age_scoped(index_payloads, ids["project"], sa.true())
    with transaction() as conn:
        jid, _ = jobs.enqueue(conn, "index_snapshot", {})
        conn.execute(
            sa.update(jobs.jobs).where(jobs.jobs.c.id == jid).values(status="dead", updated_at=OLD)
        )
    out = maintenance.run_retention(s=_settings(), dry_run=True)
    assert out["dry_run"] is True
    assert out["deleted"]["terminal_jobs"] == 1
    assert out["deleted"]["index_payloads"][ids["project"]]["payload_rows"] == 1
    with transaction() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(jobs.jobs)).scalar_one() == 1
        maintenance._scope_tenant(conn, ids["project"])
        assert (
            conn.execute(sa.select(sa.func.count()).select_from(index_payloads)).scalar_one() == 1
        )


def test_artifact_orphan_gc(client_factory) -> None:
    _ids(client_factory)
    root = maintenance._artifact_root(get_settings())
    assert root is not None
    sha = "e" * 64
    p = root / "sha256" / sha[:2] / sha
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"orphan")
    old = datetime.now(UTC) - timedelta(hours=72)
    os.utime(p, (old.timestamp(), old.timestamp()))
    with transaction() as conn:
        out = maintenance._gc_artifact_orphans(conn, _settings(), dry_run=False)
    assert out == {"artifact_orphan_files": 1, "artifact_orphan_bytes": 6}
    assert not p.exists()


def test_try_scalar_recovers_after_query_error() -> None:
    with transaction() as conn:
        assert maintenance._try_scalar(conn, "SELECT no_such_function()") is None
        assert conn.execute(sa.text("SELECT 1")).scalar_one() == 1


def test_storage_report_smoke(client_factory) -> None:
    ids = _ids(client_factory)
    _ready_payloads(ids, "f" * 40)
    report = maintenance.storage_report(s=_settings(postgres_volume_bytes=1_000_000))
    assert report["database"]["size_bytes"] > 0
    assert report["volume"]["pct_used"] is not None
    assert report["volume"]["pct_used"] > 70  # tiny configured volume → all alerts
    assert len(report["alerts"]) == 3
    names = {t["table"] for t in report["tables"]}
    assert {"jobs", "index_payloads", "assessments"} <= names
    kinds = {p["kind"] for p in report["payloads_by_kind"]}
    assert kinds == {"intelligence_index", "files"}
    assert "reclaimable" in report


def test_storage_report_includes_data_volume_alert(client_factory, tmp_path) -> None:
    client_factory()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "artifact").write_bytes(b"x" * 80)

    report = maintenance.storage_report(
        s=_settings(data_volume_path=data_dir, data_volume_bytes=100)
    )

    assert report["data_volume"] == {
        "path": str(data_dir),
        "limit_bytes": 100,
        "used_bytes": 80,
        "pct_used": 80.0,
    }
    assert any("data volume usage at 80.0%" in alert for alert in report["alerts"])


def test_storage_report_skips_data_volume_alert_when_unconfigured(client_factory, tmp_path) -> None:
    client_factory()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "artifact").write_bytes(b"x" * 80)

    report = maintenance.storage_report(s=_settings(data_volume_path=data_dir, data_volume_bytes=0))

    assert report["data_volume"]["limit_bytes"] is None
    assert report["data_volume"]["used_bytes"] == 80
    assert report["data_volume"]["pct_used"] is None
    assert not any("data volume usage at" in alert for alert in report["alerts"])


def test_storage_report_handles_missing_data_volume_path(client_factory, tmp_path) -> None:
    client_factory()

    report = maintenance.storage_report(
        s=_settings(data_volume_path=tmp_path / "missing", data_volume_bytes=100)
    )

    assert report["data_volume"]["used_bytes"] is None
    assert report["data_volume"]["pct_used"] is None
    assert not any("data volume usage at" in alert for alert in report["alerts"])


def test_run_once_posts_data_volume_alert_independently(
    client_factory, monkeypatch, tmp_path
) -> None:
    client_factory()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "artifact").write_bytes(b"x" * 80)
    posted = []
    monkeypatch.setattr(maintenance, "_post_alert", lambda _url, payload: posted.append(payload))

    report = maintenance.run_once(
        s=_settings(
            data_volume_path=data_dir,
            data_volume_bytes=100,
            postgres_volume_bytes=10_000_000_000,
            security_workdir=tmp_path / "work",
            ops_alert_webhook_url="https://alerts.invalid",
        )
    )

    assert [payload["kind"] for payload in posted] == ["data_volume_storage"]
    assert posted[0]["path"] == str(data_dir)
    assert posted[0]["pct_used"] == 80.0
    assert posted[0]["used_bytes"] == 80
    assert posted[0]["limit_bytes"] == 100
    assert posted[0]["level"] == 80
    assert "checkouts" not in posted[0]["filesystem"]
    assert "data_volume" in report


def test_ops_prometheus_includes_data_volume_percentage(
    client_factory, settings_override, tmp_path
) -> None:
    client = client_factory()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "artifact").write_bytes(b"x" * 80)
    settings_override(
        OPS_API_TOKEN="test-ops-token",
        DATA_VOLUME_PATH=str(data_dir),
        DATA_VOLUME_BYTES="100",
    )

    response = client.get(
        "/api/v1/ops/storage/prometheus",
        headers={"Authorization": "Bearer test-ops-token"},
    )

    assert response.status_code == 200
    assert "# HELP ari_data_volume_pct" in response.text
    assert "# TYPE ari_data_volume_pct gauge" in response.text
    assert "ari_data_volume_pct 80.0" in response.text


def test_ops_endpoint(client_factory, settings_override) -> None:
    client = client_factory()
    # Disabled surface: 404 whether or not an auth header is sent.
    assert client.get("/api/v1/ops/storage").status_code == 404
    assert (
        client.get("/api/v1/ops/storage", headers={"Authorization": "Bearer x"}).status_code == 404
    )
    settings_override(OPS_API_TOKEN="test-ops-token")
    assert client.get("/api/v1/ops/storage").status_code == 401
    assert (
        client.get("/api/v1/ops/storage", headers={"Authorization": "Bearer wrong"}).status_code
        == 401
    )
    ok = client.get("/api/v1/ops/storage", headers={"Authorization": "Bearer test-ops-token"})
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["database"]["size_bytes"] > 0
    prom = client.get(
        "/api/v1/ops/storage/prometheus", headers={"Authorization": "Bearer test-ops-token"}
    )
    assert prom.status_code == 200
    assert "ari_postgres_bytes" in prom.text
    dry = client.post(
        "/api/v1/ops/maintenance",
        headers={"Authorization": "Bearer test-ops-token"},
        json={"dry_run": True},
    )
    assert dry.status_code == 200
    assert dry.json()["dry_run"] is True


def test_assessment_detail_disabled_by_default(client_factory) -> None:
    ids = _ids(client_factory)
    with transaction() as conn:
        aid = new_id(IdPrefix.asm)
        conn.execute(
            sa.insert(assessments).values(
                id=aid,
                project_id=ids["project"],
                repo_id=ids["repo"],
                scope_id=ids["scope"],
                commit_sha="a" * 40,
                trigger="api",
                state="COMPLETED",
                doc={},
            )
        )
        conn.execute(
            sa.insert(assessment_events).values(
                assessment_id=aid, seq=1, type="state_changed", doc={}, created_at=OLD
            )
        )
        conn.execute(
            sa.insert(agent_runs).values(
                id=new_id(IdPrefix.evt),
                assessment_id=aid,
                agent="scout",
                status="done",
                doc={},
                created_at=OLD,
            )
        )
    # Default: disabled — nothing pruned.
    out = maintenance.run_retention(s=_settings())
    assert "assessment_events" not in out["deleted"]
    # Opt-in prunes only terminal assessments' detail.
    out = maintenance.run_retention(s=_settings(retention_assessment_detail_days=90))
    assert out["deleted"]["assessment_events"] == 1
    assert out["deleted"]["agent_runs"] == 1


def test_checkout_ref_gc(client_factory, tmp_path) -> None:
    _ids(client_factory)
    bare = tmp_path / "repos" / "r.git"
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(work),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "c",
            "--allow-empty",
        ],
        check=True,
    )
    subprocess.run(["git", "clone", "-q", "--bare", str(work), str(bare)], check=True)
    refs = []
    for i in range(8):
        env = dict(os.environ, GIT_COMMITTER_DATE=f"2026-01-0{i + 1}T00:00:00Z")
        subprocess.run(
            [
                "git",
                "-C",
                str(work),
                "-c",
                "user.email=t@t",
                "-c",
                "user.name=t",
                "commit",
                "-qm",
                f"c{i}",
                "--allow-empty",
            ],
            check=True,
            env=env,
        )
        sha = subprocess.run(
            ["git", "-C", str(work), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "-C", str(work), "push", "-q", str(bare), f"{sha}:refs/ari/{sha}"], check=True
        )
        refs.append(sha)
    s = _settings(security_workdir=tmp_path, retention_checkout_refs_keep=5)
    out = maintenance._gc_checkout_refs(s, dry_run=False)
    info = out["checkouts"]["r.git"]
    assert info["refs"] == 8 and info["prunable_refs"] == 3
    left = subprocess.run(
        ["git", "-C", str(bare), "for-each-ref", "--format=%(refname)", "refs/ari/"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert len(left) == 5
    kept_shas = {r.rsplit("/", 1)[1] for r in left}
    assert kept_shas == set(refs[3:])  # newest 5 kept


def test_maintenance_enabled_loop_gate(settings_override) -> None:
    settings_override(MAINTENANCE_ENABLED="false")
    assert maintenance.main(["loop"]) == 0


def test_projects_without_rows(client_factory) -> None:
    # A bare project with no payloads/history is a no-op, not an error.
    ids = _ids(client_factory)
    out = maintenance.run_retention(s=_settings())
    project_report = out["deleted"]["index_payloads"][ids["project"]]
    assert project_report["payload_rows"] == 0
    assert project_report["protected_snapshots"] == {
        "a_findings": 0,
        "b_verified_regression_memory": 0,
        "c_expectation_decisions": 0,
        "d_non_terminal_assessments": 0,
        "e_active_jobs": 0,
        "f_all_assessments": 0,
    }
