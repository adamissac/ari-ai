from pathlib import Path

import pytest
from intel_test_helpers import commit
from intel_test_helpers import repository as repository
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
    with pytest.raises(IntelligenceError, match="output exceeds"):
        GitReader(path).run("ls-tree", "-r", sha, limit=20)


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
def via_typed_parameter(service: Service):
    return service.other()
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
    assert any(e.callee_name == "service.other" and e.resolution == "likely" for e in parser.calls)


def test_redaction_keeps_python_parseable_and_routes_indexed(
    repository: tuple[Path, str],
) -> None:
    path, _ = repository
    secret = "hunter2-" + "z" * 12
    (path / "app/health.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        f'WEBHOOK_SECRET = "{secret}"\n'
        "@app.get('/health/ready')\n"
        "def ready(s):\n"
        "    return dict(\n"
        "        webhook_secret_configured=bool(\n"
        "            s.github_webhook_secret\n"
        "            and s.github_webhook_secret.get_secret_value() not in ('', 'replace-me')\n"
        "        ),\n"
        "    )\n"
    )
    (path / "app/settings.txt").write_text(f"DB_PASSWORD={secret} with spaces\n")
    sha = commit(path)
    files = GitReader(path).read(sha)[1]
    health = next(f for f in files if f.path == "app/health.py")
    assert secret not in "".join(f.content for f in files)
    assert 'WEBHOOK_SECRET = "[REDACTED]"' in health.content
    assert "webhook_secret_configured=bool(\n" in health.content
    parser = PythonExtractor(ref(sha), files)
    parser.extract()
    assert not [i for i in parser.issues if i.path == "app/health.py"]
    assert ("GET", "/health/ready") in {(e.method, e.path_template) for e in parser.entries}


def test_non_literal_route_paths_are_flagged_not_silently_dropped(
    repository: tuple[Path, str],
) -> None:
    path, _ = repository
    (path / "app/dynamic_routes.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        'FIXTURE_ROUTE = "/payments/pay_fixture"\n'
        'CONTROL_PATH = "/payments/control"\n\n'
        "@app.get(FIXTURE_ROUTE)\n"
        "def pay_fixture():\n"
        "    return {}\n\n"
        "@app.post(CONTROL_PATH)\n"
        "def control():\n"
        "    return {}\n\n"
        "@app.get()\n"
        "def no_path():\n"
        "    return {}\n\n"
        "@app.delete('/payments/{payment_id}')\n"
        "def remove(payment_id: str):\n"
        "    return {}\n"
    )
    sha = commit(path)
    parser = PythonExtractor(ref(sha), GitReader(path).read(sha)[1])
    parser.extract()
    reasons = [i.reason for i in parser.issues if i.path == "app/dynamic_routes.py"]
    assert len(reasons) == 3
    assert any("FIXTURE_ROUTE" in r and "pay_fixture" in r for r in reasons)
    assert any("CONTROL_PATH" in r and "control" in r for r in reasons)
    assert any("no_path" in r for r in reasons)
    # The literal route is still indexed; the dynamic ones are honestly absent.
    assert ("DELETE", "/payments/{payment_id}") in {
        (e.method, e.path_template) for e in parser.entries
    }
    handlers = {
        s.qualified_name
        for s in parser.symbols
        if any(e.handler_symbol_id == s.id for e in parser.entries)
    }
    assert "app.dynamic_routes.remove" in handlers
    assert not any(h.endswith(("pay_fixture", "control", "no_path")) for h in handlers)


def test_mid_line_secret_values_are_redacted_without_breaking_parse(
    repository: tuple[Path, str],
) -> None:
    path, _ = repository
    secret = "hunter2" + "z" * 12
    (path / "app/midline.py").write_text(
        f"def build(s):\n    return dict(password={secret}, user=s.user)\n"
    )
    (path / "app/closers.py").write_text(f"def make():\n    return f(password={secret})\n")
    (path / "app/still_code.py").write_text(
        "def sig(secret: bytes, x: int) -> bool:\n"
        "    return webhook_secret_configured and bool(secret)\n"
    )
    sha = commit(path)
    files = GitReader(path).read(sha)[1]
    assert secret not in "".join(f.content for f in files)
    midline = next(f for f in files if f.path == "app/midline.py")
    closers = next(f for f in files if f.path == "app/closers.py")
    still = next(f for f in files if f.path == "app/still_code.py")
    assert "password=[REDACTED], user=s.user" in midline.content
    assert "password=[REDACTED])" in closers.content
    # Identifiers that merely look secret-keyed keep their references.
    assert "secret: bytes" in still.content
    assert "bool(secret)" in still.content
    parser = PythonExtractor(ref(sha), files)
    parser.extract()
    assert not [
        i
        for i in parser.issues
        if i.path in {"app/midline.py", "app/closers.py", "app/still_code.py"}
    ]


_REDACT_CASES = [
    # (source, secret substrings that must be gone)
    pytest.param(
        'slack_token = "xoxb-' + "1" * 12 + "-" + "aA" * 6 + '"',
        ["xoxb-" + "1" * 12 + "-" + "aA" * 6],
        id="slack_xoxb",
    ),
    pytest.param('token = "abcdEFGHijklMNOPqrst"', ["abcdEFGHijklMNOPqrst"], id="bare_token_key"),
    pytest.param(
        'STRIPE = "sk_live_' + "x" * 15 + '"', ["sk_live_" + "x" * 15], id="stripe_sk_live"
    ),
    pytest.param(
        'DB = "postgresql://admin:S3' + "cretPw" + '@db.internal:5432/app"',
        ["admin:S3cretPw"],
        id="url_credential",
    ),
    pytest.param(
        'password = (\n    "part1abc"\n    "part2def"\n)',
        ["part1abc", "part2def"],
        id="implicit_concat",
    ),
    pytest.param('api_key = "first111", "second222"', ["first111", "second222"], id="tuple_rhs"),
    pytest.param(
        'jwt = "'
        + "eyJ"
        + "hbGciOiJIUzI1NiIs"
        + "."
        + "eyJ"
        + "zdWIiOiIxMjM0NTY3"
        + "."
        + "OeFg"
        + "hijKlmNopqrS"
        + '"',
        ["OeFghijKlmNopqrS"],
        id="jwt",
    ),
    pytest.param(
        'MAPS = "AIzaSyD-abcdefghijklmnopqrstuvwxyz12345"',
        ["AIzaSyD-abcdefghijklmnopqrstuvwxyz12345"],
        id="google_aiza",
    ),
    pytest.param(
        'S3_SECRET = """line1\nsecret-lit-9\nline3"""', ["secret-lit-9"], id="triple_quoted"
    ),
    pytest.param('d = {"password": "hunter2zzz"}', ["hunter2zzz"], id="dict_literal"),
    pytest.param("f(password=hunter2z)", ["hunter2z"], id="kwarg"),
    pytest.param('AWS = "AKIAIOSFODNN7EXAMPLE"', ["AKIAIOSFODNN7EXAMPLE"], id="aws_akia"),
    pytest.param(
        'K = """-----BEGIN PRIVATE KEY-----\nabc123xyz\n-----END PRIVATE KEY-----"""',
        ["abc123xyz"],
        id="pem_block",
    ),
    pytest.param('b = "Bearer tok_abc123def456"', ["tok_abc123def456"], id="bearer"),
    pytest.param('token = "Bearer " + "zz9" * 8', ["Bearer ", "zz9"], id="plus_concat"),
    pytest.param(
        'x_token = "one123", "two456", "three789"',
        ["one123", "two456", "three789"],
        id="tuple_three",
    ),
]


@pytest.mark.parametrize(("source", "secrets"), _REDACT_CASES)
def test_redact_removes_secret_literals_parseably(source: str, secrets: list[str]) -> None:
    import ast

    from code_intelligence.privacy import redact

    out = redact(source)
    for secret in secrets:
        assert secret not in out, f"{secret!r} leaked: {out!r}"
    ast.parse(out)  # still valid Python
    assert out.count("\n") == source.count("\n")  # line count preserved


@pytest.mark.parametrize(
    ("source", "preserved"),
    [
        pytest.param(
            "def f(secret: bytes, api_key=key):\n    return bool(secret)",
            ["secret: bytes", "api_key=key", "bool(secret)"],
            id="typed_annotations",
        ),
        pytest.param(
            'x = "literal" + variable + "other"', ['"literal"', '"other"'], id="nonsecret_concat"
        ),
        pytest.param('s = f"api_key={key}"', ["{key}"], id="fstring_expr"),
        pytest.param(
            "TOKEN_NAMES = (input_tokens, max_tokens)",
            ["input_tokens", "max_tokens"],
            id="token_fields_untouched",
        ),
    ],
)
def test_redact_preserves_non_secret_references(source: str, preserved: list[str]) -> None:
    import ast

    from code_intelligence.privacy import redact

    out = redact(source)
    for bit in preserved:
        assert bit in out, f"{bit!r} destroyed: {out!r}"
    ast.parse(out)
    assert out.count("\n") == source.count("\n")


def test_redact_documented_residuals() -> None:
    """Known-narrow leaks documented in docs/research/intel-pipeline-audit/README.md §8:
    digit-less mid-line bare tokens and os.environ.get() default values."""
    from code_intelligence.privacy import redact

    assert "hunterpass" in redact('connect(password=hunterpass, user="u")')
    assert "fallbackPw9" in redact('pw = os.environ.get("DB_PASSWORD", "fallbackPw9")')
