from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from intel_test_helpers import commit
from intel_test_helpers import repository as repository
from shared.base import utcnow
from shared.evidence import EvidenceKind, EvidenceRef
from shared.findings import (
    PatchCandidate,
    VerificationCheck,
    VerificationCheckName,
    VerificationResult,
)
from shared.intelligence import ContextPackRequest, ContextPurpose, ExpectationStatus
from shared.intelligence_memory import ExpectationDecision, ExpectationDecisionRequest

from code_intelligence.api import IntelligenceService, RepositoryBinding
from code_intelligence.memory import MemoryConflict, SQLiteMemoryStore
from code_intelligence.models import IntelligenceError
from code_intelligence.store import SQLiteIndexStore


def service(root: Path, db: Path) -> IntelligenceService:
    return IntelligenceService(
        SQLiteIndexStore(db),
        [RepositoryBinding("prj_fixture00", "rep_fixture00", "owned/fixture", root)],
    )


def test_human_decision_is_durable_visible_to_all_purposes_and_never_rewrites_index(
    repository: tuple[Path, str], tmp_path: Path
) -> None:
    root, sha = repository
    db = tmp_path / "index.db"
    engine = service(root, db)
    ref = engine.index_repository("prj_fixture00", "rep_fixture00", sha)
    before = engine.store.get(ref).model_dump_json()
    exp = engine.expectations(ref, subject="app.payments.read_payment")[0]
    request = ContextPackRequest(
        snapshot_ref=ref, purpose="review", focus=["app.payments.read_payment"]
    )
    original_pack = engine.build_context_pack(request)
    decision = engine.decide_expectation(
        ref,
        exp.id,
        ExpectationDecisionRequest(
            status="confirmed",
            reason="Owner confirms each customer must only read their own payment",
            expected_revision=0,
        ),
        actor_id="usr_fixture00",
    )
    assert decision.revision == 1
    restarted = service(root, db)
    effective = next(e for e in restarted.expectations(ref) if e.id == exp.id)
    assert effective.status is ExpectationStatus.confirmed
    assert effective.sources[-1].kind is EvidenceKind.human_input
    assert restarted.store.get(ref).model_dump_json() == before
    for purpose in ["review", "scout", "trace", "verify", "monitoring"]:
        pack = restarted.build_context_pack(
            request.model_copy(update={"purpose": ContextPurpose(purpose)})
        )
        assert "Owner confirms" in pack.model_dump_json()
        assert "authenticated-human:usr_fixture00" in pack.model_dump_json()
        assert pack.token_count <= pack.token_budget
    assert restarted.build_context_pack(request).id != original_pack.id
    with pytest.raises(MemoryConflict):
        restarted.decide_expectation(
            ref,
            exp.id,
            ExpectationDecisionRequest(
                status="rejected", reason="A conflicting decision", expected_revision=0
            ),
            actor_id="usr_fixture01",
        )
    (root / "README.md").write_text("Changed unrelated documentation\n")
    head = commit(root)
    next_ref = restarted.index_repository("prj_fixture00", "rep_fixture00", head)
    assert restarted.memory is not None
    assert restarted.memory.decisions(next_ref) == []
    assert restarted.decision_history(ref, exp.id)[0] == decision


def test_concurrent_decisions_are_serialized_and_history_paginated(tmp_path: Path) -> None:
    from shared.intelligence import SnapshotRef

    ref = SnapshotRef(
        project_id="prj_fixture00",
        repo_id="rep_fixture00",
        snapshot_id="snp_fixture00",
        commit_sha="a" * 40,
        index_version="fixture",
    )
    memory = SQLiteMemoryStore(tmp_path / "memory.db")

    def write(actor: str) -> str:
        decision = ExpectationDecision(
            snapshot_ref=ref,
            expectation_id="exp_fixture00",
            status="confirmed",
            reason="Authenticated owner rule",
            expected_revision=0,
            revision=1,
            decided_by=actor,
            decided_at=utcnow(),
        )
        try:
            memory.put_decision(decision)
            return "saved"
        except MemoryConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, ["usr_fixture00", "usr_fixture01"])) == ["conflict", "saved"]
    assert len(memory.history(ref, "exp_fixture00", limit=1)) == 1
    assert memory.history(ref, "exp_fixture00", after=1) == []


def test_only_complete_independent_candidate_proof_enters_context(
    repository: tuple[Path, str], tmp_path: Path
) -> None:
    root, sha = repository
    engine = service(root, tmp_path / "index.db")
    ref = engine.index_repository("prj_fixture00", "rep_fixture00", sha)
    patch = PatchCandidate(
        id="pat_fixture00",
        finding_id="fnd_fixture00",
        attempt=1,
        diff_artifact_id="art_fixture00",
        diff_sha256="b" * 64,
        base_commit_sha=sha,
        worktree_ref="isolated-fixture",
        files_changed=["app/payments.py", "tests/test_owned.py"],
        tests_added=["tests/test_owned.py::test_ownership"],
        produced_by_run_id="run_patch0000",
        rationale="fixture",
        created_at=utcnow(),
    )
    evidence = EvidenceRef(
        kind="sandbox_run",
        artifact_id="art_fixture01",
        sha256="c" * 64,
        commit_sha=sha,
        provenance="trusted Verify fixture",
    )
    verification = VerificationResult(
        id="ver_fixture00",
        patch_id=patch.id,
        verdict="accepted",
        checks=[
            VerificationCheck(name=n, passed=True, evidence=[evidence])
            for n in VerificationCheckName
        ],
        sandbox_run_ids=["sandbox-fixture-verify"],
        produced_by_run_id="run_verify000",
        created_at=utcnow(),
    )
    with pytest.raises(IntelligenceError):
        engine.register_verified_regression(
            ref, patch, verification.model_copy(update={"checks": verification.checks[:1]})
        )
    with pytest.raises(IntelligenceError):
        engine.register_verified_regression(
            ref,
            patch,
            verification.model_copy(update={"produced_by_run_id": patch.produced_by_run_id}),
        )
    record = engine.register_verified_regression(ref, patch, verification)
    engine.register_verified_regression(ref, patch, verification)
    restarted = service(root, tmp_path / "index.db")
    assert restarted.memory is not None
    assert restarted.memory.regressions(ref) == [record]
    pack = restarted.build_context_pack(
        ContextPackRequest(snapshot_ref=ref, purpose="verify", focus=[patch.finding_id])
    )
    text = pack.model_dump_json()
    assert "CANDIDATE" in text and "not proof of merge" in text
    assert "tests/test_owned.py" in text
    assert any(p.artifact_id == "art_fixture01" for p in pack.provenance)
    with pytest.raises(MemoryConflict):
        restarted.memory.put_regression(
            record.model_copy(update={"verification_id": "ver_fixture01"})
        )
