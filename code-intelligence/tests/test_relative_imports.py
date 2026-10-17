"""Relative imports must stay inside the statically known package boundary."""

from pathlib import Path

import pytest
from intel_test_helpers import commit, git
from intel_test_helpers import repository as repository
from shared.intelligence_memory import ExpectationDecisionRequest

from code_intelligence.api import IntelligenceService, RepositoryBinding
from code_intelligence.models import INDEX_VERSION
from code_intelligence.store import SQLiteIndexStore


def service(root: Path, db: Path) -> IntelligenceService:
    return IntelligenceService(
        SQLiteIndexStore(db),
        [RepositoryBinding("prj_fixture00", "rep_fixture00", "owned/import-fixture", root)],
    )


def fixture_repo(tmp_path: Path, module: str, relative: str, alias: str) -> tuple[Path, str]:
    root = tmp_path / "target"
    root.mkdir()
    git(root, "init", "-q")
    files = {
        "outside.py": "def helper():\n    return 1\n",
        "app/__init__.py": "# package\n",
        "app/outside.py": "def helper():\n    return 2\n",
        "app/nested/__init__.py": "# nested package\n",
        module: f"from {relative} import helper as {alias}\ndef run():\n    return {alias}()\n",
    }
    for path, content in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return root, commit(root)


@pytest.mark.parametrize("alias", ["helper", "renamed"])
@pytest.mark.parametrize(
    ("module", "relative"),
    [
        ("service.py", ".outside"),
        ("app/service.py", "..outside"),
        ("app/nested/service.py", "...outside"),
        ("app/__init__.py", "..outside"),
    ],
)
def test_out_of_package_import_never_becomes_an_exact_top_level_call(
    tmp_path: Path, module: str, relative: str, alias: str
) -> None:
    root, sha = fixture_repo(tmp_path, module, relative, alias)
    engine = service(root, tmp_path / "index.db")
    ref = engine.index_repository("prj_fixture00", "rep_fixture00", sha)
    index = engine.store.get(ref)
    edge = next(edge for edge in index.calls if edge.callee_name == alias)
    assert edge.callee_id is None
    assert edge.resolution.value == "unresolved"
    binding = next(item for item in index.imports if item.path == module)
    assert binding.module == relative
    assert any(
        issue.path == module and "relative import" in issue.reason.lower() for issue in index.issues
    )


@pytest.mark.parametrize("alias", ["helper", "renamed"])
@pytest.mark.parametrize(
    ("module", "relative"),
    [
        ("app/service.py", ".outside"),
        ("app/nested/service.py", "..outside"),
        ("app/nested/__init__.py", "..outside"),
    ],
)
def test_valid_relative_import_stays_grounded_in_its_package(
    tmp_path: Path, module: str, relative: str, alias: str
) -> None:
    root, sha = fixture_repo(tmp_path, module, relative, alias)
    engine = service(root, tmp_path / "index.db")
    ref = engine.index_repository("prj_fixture00", "rep_fixture00", sha)
    index = engine.store.get(ref)
    edge = next(edge for edge in index.calls if edge.callee_name == alias)
    symbols = {symbol.id: symbol for symbol in index.symbols}
    assert edge.resolution.value == "exact"
    assert edge.callee_id is not None
    assert symbols[edge.callee_id].qualified_name == "app.outside.helper"
    assert not any(issue.path == module for issue in index.issues)


def test_parser_revision_creates_new_facts_without_relabeling_old_memory(
    repository: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, sha = repository
    engine = service(root, tmp_path / "index.db")
    monkeypatch.setattr("code_intelligence.ingest.INDEX_VERSION", "python-ast-ts/0.3.0")
    old = engine.index_repository("prj_fixture00", "rep_fixture00", sha)
    original = engine.store.get(old).model_dump_json()
    expectation = engine.expectations(old, subject="app.payments.read_payment")[0]
    engine.decide_expectation(
        old,
        expectation.id,
        ExpectationDecisionRequest(
            status="confirmed", reason="Prior parser intent", expected_revision=0
        ),
        actor_id="usr_fixture00",
    )
    monkeypatch.setattr("code_intelligence.ingest.INDEX_VERSION", INDEX_VERSION)
    current = engine.index_repository("prj_fixture00", "rep_fixture00", sha)
    assert current != old
    assert current.commit_sha == old.commit_sha
    assert engine.store.get(old).model_dump_json() == original
    assert engine.memory is not None and engine.memory.decisions(current) == []
    assert engine.decision_history(old, expectation.id)[0].reason == "Prior parser intent"
