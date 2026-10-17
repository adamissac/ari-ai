"""Owned target acceptance: index only; never import or execute target application code."""

import shutil
from pathlib import Path

from intel_test_helpers import commit, git
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


def test_vulnerable_route_gets_cited_ownership_convention_and_fix_invalidates_it(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    target = tmp_path / "target"
    shutil.copytree(root / "examples/payments-lite/target", target)
    git(target, "init", "-q")
    base_sha = commit(target)
    engine = IntelligenceService(
        SQLiteIndexStore(tmp_path / "index.sqlite"),
        [RepositoryBinding("prj_payments00", "rep_payments00", "owned/payments", target)],
    )
    base = engine.index_repository("prj_payments00", "rep_payments00", base_sha)
    index = engine.store.get(base)
    route = next(e for e in index.entry_points if e.path_template == "/payments/{payment_id}")
    assert route.auth_dependencies == ["current_customer"]
    assert all("get_store" not in e.auth_dependencies for e in index.entry_points)
    siblings = [
        e
        for e in index.entry_points
        if e.path_template
        in {
            "/customers/{customer_id}",
            "/refunds/{refund_id}",
        }
    ]
    assert len(siblings) == 2 and all("require_owner" in e.auth_dependencies for e in siblings)
    rules = engine.expectations(base, route.id)
    conventions = [e for e in rules if "Possible ownership inconsistency" in e.statement]
    assert len(conventions) == 1 and conventions[0].kind == "ownership"
    assert conventions[0].confidence == 0.6 and conventions[0].status == "ambiguous"
    assert len(conventions[0].sources) == 2
    assert all(p.commit_sha == base_sha and "Sibling GET" in p.note for p in conventions[0].sources)
    assert any("Module rule" in (p.note or "") for e in rules for p in e.sources)
    pack = engine.build_context_pack(
        ContextPackRequest(
            snapshot_ref=base, purpose="scout", focus=[conventions[0].id], token_budget=24_000
        )
    )
    assert any("Possible ownership inconsistency" in c.content for c in pack.chunks)
    assert any("get_payment" in (p.symbol or "") for p in pack.provenance)

    # Add the same helper used by siblings; the convention warning must disappear at head.
    handler = engine.get_symbol(base, route.handler_symbol_id)
    file = target / handler.path
    lines = file.read_text().splitlines()
    return_line = lines[handler.end_line - 1]
    indent = return_line[: len(return_line) - len(return_line.lstrip())]
    lines.insert(handler.end_line - 1, indent + "require_owner(p.customer_id, customer)")
    file.write_text("\n".join(lines) + "\n")
    head_sha = commit(target, "restore ownership convention")
    head = engine.index_repository("prj_payments00", "rep_payments00", head_sha, base_snapshot=base)
    head_route = next(
        e for e in engine.entry_points(head) if e.path_template == "/payments/{payment_id}"
    )
    assert "require_owner" in head_route.auth_dependencies
    assert not any(
        "Possible ownership inconsistency" in e.statement
        for e in engine.expectations(head, head_route.id)
    )
    assert (
        conventions[0].id
        in engine.affected_by_diff("rep_payments00", base_sha, head_sha).expectations
    )
