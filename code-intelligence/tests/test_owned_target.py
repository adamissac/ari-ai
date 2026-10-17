"""Owned target acceptance: index only; never import or execute target application code."""

from pathlib import Path

from intel_test_helpers import git
from shared.intelligence import ContextPack, ContextPackRequest

from code_intelligence.api import IntelligenceService, RepositoryBinding
from code_intelligence.retrieval import estimate
from code_intelligence.store import SQLiteIndexStore


def test_actual_payments_target_and_canonical_consumer_fixture(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    sha = git(root, "rev-parse", "HEAD")
    engine = IntelligenceService(
        SQLiteIndexStore(tmp_path / "index.sqlite"),
        [
            RepositoryBinding(
                "prj_payments00",
                "rep_payments00",
                "owned/payments",
                root,
                "examples/payments-lite/target",
            )
        ],
    )
    ref = engine.index_repository("prj_payments00", "rep_payments00", sha)
    index = engine.store.get(ref)
    assert all("/target/" in path for path in index.tree_files)
    assert not any("labels" in path or "label_checks" in path for path in index.tree_files)
    routes = {(e.method, e.path_template) for e in index.entry_points}
    assert {("GET", "/payments/{payment_id}"), ("POST", "/refunds")} <= routes
    assert any(e.kind == "ownership" for e in index.expectations)
    assert any("refund" in e.statement.lower() for e in index.expectations)
    pack = engine.build_context_pack(
        ContextPackRequest(
            snapshot_ref=ref, purpose="scout", focus=["/payments/{payment_id}"], token_budget=24_000
        )
    )
    assert all(p.commit_sha == sha for p in pack.provenance)
    assert any("get_payment" in (p.symbol or "") for p in pack.provenance)
    assert pack.token_count <= pack.token_budget
    fixture = root / "code-intelligence/fixtures/payments-context-pack.json"
    parsed = ContextPack.model_validate_json(fixture.read_text())
    assert estimate(parsed.model_dump_json()) <= parsed.token_count <= parsed.token_budget
