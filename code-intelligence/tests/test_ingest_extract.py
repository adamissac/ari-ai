from pathlib import Path

import pytest
from conftest import commit
from shared.intelligence import SnapshotRef

from code_intelligence.extract import PythonExtractor, dependencies
from code_intelligence.ingest import GitReader, Limits
from code_intelligence.models import INDEX_VERSION, IntelligenceError


def ref(sha: str) -> SnapshotRef:
    return SnapshotRef(
        project_id="prj_fixture00",
        repo_id="rep_fixture00",
        commit_sha=sha,
        snapshot_id="snp_fixture00",
        index_version=INDEX_VERSION,
    )


def test_pinned_objects_and_no_execution(repository: tuple[Path, str]) -> None:
    path, sha = repository
    (path / "app/payments.py").write_text('raise RuntimeError("never execute me")\n')
    (path / ".gitignore").write_text("app/\n")  # dirty rules must not affect pinned ingestion
    tree, files, issues = GitReader(path).read(sha)
    assert len(tree) == 40
    assert not issues
    assert "def refund" in next(f.content for f in files if f.path == "app/payments.py")
    assert [f.model_dump() for f in files] == [f.model_dump() for f in GitReader(path).read(sha)[1]]
    with pytest.raises(IntelligenceError, match="full lowercase"):
        GitReader(path).read("HEAD")


def test_exclusions_ignores_and_redaction(repository: tuple[Path, str], tmp_path: Path) -> None:
    path, _ = repository
    outside = tmp_path / "outside.py"
    outside.write_text("outside_secret = 'must not read'\n")
    (path / "link.py").symlink_to(outside)
    (path / ".env").write_text("PRIVATE_VALUE=unrelated\n")
    (path / "app/generated.py").write_text("# @generated\ndef generated(): pass\n")
    (path / "app/secret.py").write_text('API_KEY = "' + "sk-ant-" + "x" * 30 + '"\n')
    (path / ".gitignore").write_text("README.md\n")
    sha = commit(path)
    _, files, issues = GitReader(path).read(sha)
    assert {".env", "link.py", "README.md", "app/generated.py"} <= {i.path for i in issues}
    assert "sk-ant-" not in "".join(f.content for f in files)
    assert "outside_secret" not in "".join(f.content for f in files)
    with pytest.raises(IntelligenceError, match="max_files"):
        GitReader(path, Limits(max_files=1)).read(sha)


def test_graph_routes_test_intent_and_determinism(repository: tuple[Path, str]) -> None:
    path, sha = repository
    files = GitReader(path).read(sha)[1]
    parser = PythonExtractor(ref(sha), files)
    parser.extract()
    symbols = {s.qualified_name: s for s in parser.symbols}
    handler = symbols["app.payments.read_payment"]
    assert handler.start_line == 9  # decorators are included in source spans
    route = parser.entries[0]
    assert (route.method, route.path_template, route.auth_dependencies) == (
        "GET",
        "/payments/{payment_id}",
        ["current_user"],
    )
    assert any(
        e.caller_id == handler.id and e.callee_id == symbols["app.auth.current_user"].id
        for e in parser.calls
    )
    assert any(
        e.callee_id == symbols["app.payments.refund"].id and e.resolution == "exact"
        for e in parser.calls
    )
    assert any(e.callee_name == "callback" and e.resolution == "unresolved" for e in parser.calls)
    assert any(
        "refund_bounds" in e.statement and e.sources[0].span.start_line == 4
        for e in parser.expectations
    )
    assert all(e.status == "ambiguous" for e in parser.expectations)  # extraction is not execution
    assert dependencies(files)[0].name == "fastapi"
    again = PythonExtractor(ref(sha), files)
    again.extract()
    assert parser.symbols == again.symbols
    assert parser.calls == again.calls
    assert parser.expectations == again.expectations


def test_flask_async_classes_and_unresolved_shadowing(repository: tuple[Path, str]) -> None:
    path, _ = repository
    (path / "views.py").write_text("""from flask import Flask
app = Flask(__name__)
def helper(): return 1
@app.route("/refund", methods=["POST"])
@login_required
async def endpoint(helper):
    return helper()
class Service:
    def method(self):
        return self.other()
    def other(self): return 2
""")
    sha = commit(path)
    parser = PythonExtractor(ref(sha), GitReader(path).read(sha)[1])
    parser.extract()
    assert any(
        e.path_template == "/refund"
        and e.method == "POST"
        and e.auth_dependencies == ["login_required"]
        for e in parser.entries
    )
    assert any(e.callee_name == "helper" and e.resolution == "unresolved" for e in parser.calls)
    assert any(e.callee_name == "self.other" and e.resolution == "likely" for e in parser.calls)
