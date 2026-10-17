"""Cached immutable facts must match the requested ingestion configuration."""

from __future__ import annotations

from pathlib import Path

import pytest
from intel_test_helpers import commit
from intel_test_helpers import repository as repository
from shared.base import utcnow
from shared.intelligence import ContextPackRequest, Snapshot, SnapshotStatus
from shared.intelligence_memory import ExpectationDecisionRequest

from code_intelligence.api import IntelligenceService, RepositoryBinding
from code_intelligence.ingest import Limits
from code_intelligence.models import IntelligenceError
from code_intelligence.store import SQLiteIndexStore


def service(
    root: Path, db: Path, prefix: str = "", limits: Limits | None = None
) -> IntelligenceService:
    return IntelligenceService(
        SQLiteIndexStore(db),
        [
            RepositoryBinding(
                "prj_fixture00",
                "rep_fixture00",
                "owned/fixture",
                root,
                include_prefix=prefix,
            )
        ],
        limits=limits,
    )


def test_same_commit_different_prefix_never_reuses_the_wrong_coverage(
    repository: tuple[Path, str], tmp_path: Path
) -> None:
    root, sha = repository
    db = tmp_path / "index.db"
    full = service(root, db)
    full_ref = full.index_repository("prj_fixture00", "rep_fixture00", sha)
    expectation = full.expectations(full_ref, subject="app.payments.read_payment")[0]
    full.decide_expectation(
        full_ref,
        expectation.id,
        ExpectationDecisionRequest(
            status="confirmed",
            reason="Fixture owner confirms original profile only",
            expected_revision=0,
        ),
        actor_id="usr_fixture00",
    )
    narrowed = service(root, db, "app")
    app_ref = narrowed.index_repository("prj_fixture00", "rep_fixture00", sha)
    assert app_ref != full_ref
    assert app_ref.commit_sha == full_ref.commit_sha
    assert len(app_ref.index_version) <= 80  # PostgreSQL's existing version column
    assert narrowed.memory is not None and narrowed.memory.decisions(app_ref) == []
    assert all(e.origin.value != "human_input" for e in narrowed.expectations(app_ref))
    assert all(s.path.startswith("app/") for s in narrowed.symbols(app_ref))
    assert any(s.path.startswith("tests/") for s in full.symbols(full_ref))
    assert (
        service(root, db, "./app/").index_repository("prj_fixture00", "rep_fixture00", sha)
        == app_ref
    )
    # Historical refs remain valid and immutable; no decision or fact is relabelled.
    assert full.store.get(full_ref).ref == full_ref
    packet = narrowed.build_context_pack(
        ContextPackRequest(
            snapshot_ref=app_ref, purpose="review", focus=["app.payments.read_payment"]
        )
    )
    assert packet.snapshot_ref == app_ref
    assert all(p.provenance.endswith(app_ref.index_version) for p in packet.provenance)
    assert all(not c.provenance.path or c.provenance.path.startswith("app/") for c in packet.chunks)


def test_changed_limits_have_a_distinct_profile_and_cannot_bypass_a_narrow_budget(
    repository: tuple[Path, str], tmp_path: Path
) -> None:
    root, sha = repository
    db = tmp_path / "index.db"
    original = service(root, db).index_repository("prj_fixture00", "rep_fixture00", sha)
    small = service(root, db, limits=Limits(max_file_bytes=1))
    limited = small.index_repository("prj_fixture00", "rep_fixture00", sha)
    assert limited != original
    assert all(s.path == "app/__init__.py" for s in small.symbols(limited))
    assert all(len(f.content.encode()) <= 1 for f in small.store.get(limited).files)
    assert small.store.get(limited).issues
    assert service(root, db).index_repository("prj_fixture00", "rep_fixture00", sha) == original


@pytest.mark.parametrize("prefix", ["../app", "/app", "app\\nested"])
def test_invalid_prefix_is_rejected_before_any_cache_hit(
    repository: tuple[Path, str], tmp_path: Path, prefix: str
) -> None:
    root, sha = repository
    db = tmp_path / "index.db"
    service(root, db).index_repository("prj_fixture00", "rep_fixture00", sha)
    with pytest.raises(IntelligenceError, match="prefix"):
        service(root, db, prefix).index_repository("prj_fixture00", "rep_fixture00", sha)


def test_backend_and_diff_queries_select_the_same_scoped_version(
    repository: tuple[Path, str], tmp_path: Path
) -> None:
    root, base = repository
    db = tmp_path / "index.db"
    scoped = service(root, db, "app")
    pending = Snapshot(
        id="snp_profile00",
        repo_id="rep_fixture00",
        commit_sha=base,
        status=SnapshotStatus.pending,
        index_version="pending",
        created_at=utcnow(),
    )
    ready = scoped.index_snapshot(pending, "owned/fixture")
    assert ready.status is SnapshotStatus.ready
    ref = scoped.index_repository("prj_fixture00", "rep_fixture00", base)
    assert ready.id == ref.snapshot_id and ready.index_version == ref.index_version
    with (root / "app/payments.py").open("a") as out:
        out.write("\nPROFILE_FIXTURE = True\n")
    head = commit(root)
    scoped.index_repository("prj_fixture00", "rep_fixture00", head)
    impact = service(root, db, "./app/").affected_by_diff("rep_fixture00", base, head)
    assert impact.base_snapshot_id == ref.snapshot_id
    assert impact.changed_paths == ["app/payments.py"]
