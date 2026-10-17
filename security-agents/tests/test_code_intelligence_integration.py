"""Integration with Sarosh's real `code_intelligence` index (not a stub).

This indexes `examples/payments-lite/target` with `IntelligenceService`, wraps
the result in `CodeIntelligenceAdapter`, and checks that the agents' tools work
against it — in particular that the structural signal Scout depends on (the
planted route missing the ownership helper its siblings call) survives the real
index.

Skips when `code_intelligence` is not importable.
"""

from __future__ import annotations

import subprocess

import pytest

from security_agents.contracts import AgentName
from security_agents.tools import default_registry, wire_name

from .conftest import PAYMENTS_LITE_DIR, make_ctx, make_scope

code_intelligence = pytest.importorskip("code_intelligence.api", reason="code_intelligence not importable")
from code_intelligence.api import IntelligenceService, RepositoryBinding  # noqa: E402
from code_intelligence.store import SQLiteIndexStore  # noqa: E402

PROJECT_ID = "prj_01INTEGRATION"
REPO_ID = "rep_01INTEGRATION"


@pytest.fixture(scope="module")
def indexed(tmp_path_factory):
    """A real index of the owned target at a real git commit."""
    tmp = tmp_path_factory.mktemp("intel")
    repo = tmp / "repo"
    repo.mkdir()
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.test",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.test",
    }
    from security_agents.sandbox.workspace import copy_tree

    copy_tree(PAYMENTS_LITE_DIR / "target", repo / "target")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "payments-lite"], cwd=repo, check=True, env=env)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True, env=env
    ).stdout.strip()

    store = SQLiteIndexStore(tmp / "index.sqlite")
    service = IntelligenceService(
        store,
        repositories=[
            RepositoryBinding(
                project_id=PROJECT_ID,
                repo_id=REPO_ID,
                full_name="owner/payments-lite",
                local_path=repo,
                include_prefix="target",
            )
        ],
    )
    ref = service.index_repository(PROJECT_ID, REPO_ID, sha)
    return service, ref, repo / "target", sha


@pytest.fixture
def adapter(indexed):
    from security_agents.intel.code_intelligence_adapter import CodeIntelligenceAdapter

    service, ref, workspace, _sha = indexed
    return CodeIntelligenceAdapter(service=service, ref=ref, workspace=workspace)


def test_the_index_is_pinned_to_the_real_commit(adapter, indexed):
    _service, _ref, _workspace, sha = indexed
    assert adapter.snapshot.commit_sha == sha
    assert len(sha) == 40
    assert adapter.snapshot.pinned_by == "code_intelligence"
    provenance = adapter.provenance()
    assert provenance["status"] == "live index (code_intelligence.api)"
    assert provenance["expectations_origin"] == "derived by code_intelligence"


def test_symbols_and_entry_points_come_from_the_index(adapter):
    names = {s.qualified_name.rsplit(".", 1)[-1] for s in adapter.symbols()}
    assert {"get_payment", "get_customer", "create_refund", "require_owner"} <= names
    routes = {(e.method, e.path_template) for e in adapter.entry_points()}
    assert ("GET", "/payments/{payment_id}") in routes
    assert ("POST", "/refunds") in routes


def test_the_planted_route_is_the_one_without_the_ownership_helper(adapter):
    """The signal Scout reasons from, through the real call graph."""
    planted = adapter.neighbors("get_payment")
    assert not any("require_owner" in callee for callee in planted["callees"]), planted["callees"]
    for sibling in ("get_customer", "get_refund", "create_refund"):
        callees = adapter.neighbors(sibling)["callees"]
        assert any("require_owner" in callee for callee in callees), (sibling, callees)
    # require_owner's callers are exactly the routes that enforce ownership
    callers = {c.rsplit(".", 1)[-1] for c in adapter.neighbors("require_owner")["callers"]}
    assert "get_payment" not in callers
    assert {"get_customer", "get_refund", "create_refund"} <= callers


def test_call_resolution_quality_is_visible(adapter):
    """An unresolved or ambiguous edge must be labelled, not silently dropped."""
    labelled = [
        callee
        for symbol in ("get_payment", "create_refund")
        for callee in adapter.neighbors(symbol)["callees"]
    ]
    assert labelled
    for callee in labelled:
        assert "(" not in callee or any(
            marker in callee for marker in ("likely", "unresolved", "ambiguous")
        ), callee


def test_read_span_is_numbered_and_bounded(adapter):
    handler = adapter.find_symbol("get_payment")
    assert handler is not None
    span = adapter.read_span(handler.path, handler.start_line, handler.end_line)
    assert "def get_payment" in span.content
    assert f"{handler.start_line:>5}  " in span.content
    # a span past the end of the file is refused by the service
    from security_agents.contracts import PlatformError

    with pytest.raises(PlatformError):
        adapter.read_span(handler.path, 99_000, 99_010)


def test_expectations_come_from_the_index_when_derived(adapter):
    expectations = adapter.expectations()
    # The index may derive none yet; what matters is the shape and the origin.
    for expectation in expectations:
        assert expectation.snapshot_id == adapter.snapshot.snapshot_id
        assert expectation.statement
        assert expectation.origin in ("test", "doc", "spec", "inferred", "fixture")
        for source in expectation.sources:
            if source.path:
                assert not source.path.startswith("target/"), "paths must be snapshot-relative"


def test_registry_tools_work_against_the_real_index(adapter):
    """The agents' tools are unchanged by swapping the intelligence source."""
    registry = default_registry()
    ctx = make_ctx(AgentName.SCOUT, intel=adapter, scope=make_scope())
    handler = adapter.find_symbol("get_payment")
    read = registry.invoke(
        ctx,
        wire_name("code.read_span"),
        {"path": handler.path, "start_line": handler.start_line, "end_line": handler.end_line},
    )
    assert read.ok and "get_payment" in read.payload["content"]
    assert read.payload["sha"] == adapter.snapshot.commit_sha

    graph = registry.invoke(ctx, wire_name("graph.neighbors"), {"symbol": "get_customer"})
    assert graph.ok and any("require_owner" in c for c in graph.payload["callees"])

    search = registry.invoke(ctx, wire_name("code.search"), {"pattern": "require_owner"})
    assert search.ok and search.payload["count"] >= 1
    assert all(hit["path"] for hit in search.payload["hits"])

    analyze = registry.invoke(ctx, wire_name("static.analyze"), {"path": "payments_lite/app.py"})
    assert analyze.ok and analyze.payload["functions"]


def test_workspace_must_match_the_indexed_snapshot(adapter, tmp_path):
    """Executing against a tree that is not the indexed commit is refused."""
    from security_agents.contracts import ErrorCode, PlatformError
    from security_agents.intel.code_intelligence_adapter import CodeIntelligenceAdapter

    adapter.verify_workspace()  # the real workspace passes
    empty = tmp_path / "empty"
    empty.mkdir()
    mismatched = CodeIntelligenceAdapter(service=adapter.service, ref=adapter.ref, workspace=empty)
    with pytest.raises(PlatformError) as exc:
        mismatched.verify_workspace()
    assert exc.value.code is ErrorCode.SNAPSHOT_NOT_READY


def test_scout_runs_end_to_end_against_the_real_index(adapter):
    """A scripted Scout step, with every tool call served by the real index."""
    from security_agents.agents import scout as scout_agent
    from security_agents.contracts import Budget
    from security_agents.llm import FakeLLM, ProviderGateway
    from security_agents.runtime import run_agent

    from . import fake_agents

    gateway = ProviderGateway(FakeLLM({AgentName.SCOUT: fake_agents.scout_script()}))
    data = scout_agent.ScoutInput(
        assessment_id="asm_01INTEGRATION",
        snapshot_id=adapter.snapshot.snapshot_id,
        commit_sha=adapter.snapshot.commit_sha,
        expectation_ids=[e.id for e in adapter.expectations()],
        max_hypotheses=3,
        available_check_categories=["access_control.ownership"],
    )
    outcome = run_agent(
        scout_agent.SPEC,
        gateway=gateway,
        registry=default_registry(),
        ctx=make_ctx(AgentName.SCOUT, intel=adapter, scope=make_scope()),
        task_prompt=scout_agent.build_prompt(data, adapter),
        budget=Budget(max_tokens=500_000, max_usd=5.0, max_wall_clock_s=120.0),
    )
    assert outcome.ok, outcome.run.error_detail
    assert outcome.record.tool_names(), "the step made no tool call"
    hypotheses = scout_agent.to_hypotheses(outcome.output, data, adapter)
    assert hypotheses, "citations should validate against the real snapshot"
    assert hypotheses[0].cited_spans[0].sha == adapter.snapshot.commit_sha
    assert hypotheses[0].weakness_class == "CWE-639"
    assert hypotheses[0].expectation_ids
    assert set(hypotheses[0].expectation_ids) <= {item.id for item in adapter.expectations()}



def test_host_uses_bound_commit_and_upstream_index_despite_dirty_checkout(indexed, tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    from security_agents.intel.host import bound_intelligence

    service, ref, workspace, sha = indexed
    bindings = tmp_path / "bindings.json"
    bindings.write_text(
        json.dumps([{"repo_id": REPO_ID, "local_path": str(workspace.parent), "subdir": "target"}])
    )
    monkeypatch.setenv("REPOSITORY_BINDINGS_FILE", str(bindings))
    source = workspace / "payments_lite" / "app.py"
    original = source.read_bytes()
    try:
        source.write_text("raise RuntimeError('dirty checkout must never execute')")
        host = SimpleNamespace(
            project_id=PROJECT_ID,
            repo_id=REPO_ID,
            assessment=SimpleNamespace(commit_sha=sha, snapshot_id=ref.snapshot_id),
        )
        adapter = bound_intelligence(host, tmp_path / "worker", service)
        assert adapter.snapshot.commit_sha == sha
        assert (adapter.snapshot.root / "payments_lite" / "app.py").read_bytes() == original
        assert adapter.ref == ref
        assert adapter.find_symbol("get_payment") is not None
    finally:
        source.write_bytes(original)


def test_host_refuses_an_unregistered_repository(indexed, tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    from security_agents.contracts import ErrorCode, PlatformError
    from security_agents.intel.host import bound_intelligence

    path = tmp_path / "bindings.json"
    path.write_text(json.dumps([]))
    monkeypatch.setenv("REPOSITORY_BINDINGS_FILE", str(path))
    with pytest.raises(PlatformError) as exc:
        bound_intelligence(SimpleNamespace(repo_id=REPO_ID), tmp_path, indexed[0])
    assert exc.value.code is ErrorCode.SNAPSHOT_NOT_READY


def test_bound_host_prefers_shared_index_and_attaches_snapshot(indexed, tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    from security_agents.intel.host import bound_intelligence

    service, ref, workspace, sha = indexed
    path = tmp_path / "bindings.json"
    path.write_text(json.dumps([{"repo_id": REPO_ID, "local_path": str(workspace.parent), "subdir": "target"}]))
    monkeypatch.setenv("REPOSITORY_BINDINGS_FILE", str(path))
    monkeypatch.delenv("INTELLIGENCE_REPOSITORIES_FILE", raising=False)
    monkeypatch.delenv("INTELLIGENCE_DB_PATH", raising=False)
    calls, attached = [], []

    def shared_factory(*, include_prefix):
        calls.append(include_prefix)
        return service

    host = SimpleNamespace(
        project_id=PROJECT_ID, repo_id=REPO_ID,
        assessment=SimpleNamespace(commit_sha=sha, snapshot_id=ref.snapshot_id),
        intelligence_service=shared_factory, attach_snapshot=attached.append,
    )
    result = bound_intelligence(host, tmp_path / "worker")
    assert result.service is service
    assert calls == ["target"]
    assert attached == [ref]
    assert result.ref == ref
