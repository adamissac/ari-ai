"""JavaScript generated tests: static policy, project-import check, report parsing, and the
toolbox routing a `.test.js` through the sandbox's nodetest path (fake driver here; a real
vitest run is the opt-in `RUN_NODE_SANDBOX=1` test below)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from cr_fakes import InMemoryHost, fake
from cr_scenarios import _commit, _init, _write

from code_review.node_tests import check_js_test_source, imports_project, parse_report
from code_review.ports import CaseResult, ExecResult, RepoSource
from code_review.sandbox import SandboxPolicyError, classify, run_targets
from code_review.tools import ReviewBudget, ReviewerToolbox, RunTestsIn, ToolDenied, WriteTestIn
from code_review.workspace import Workspace

KEY_JS = """/* '_' is escaped first so 'a/b' and 'a__b' cannot collide. */
export function lessonKey(path) {
  return String(path || '').replace(/\\//g, '__').replace(/_/g, '_5F');
}
"""
GOOD_TEST = """import { describe, it, expect } from 'vitest';
import { lessonKey } from '../../src/key.js';

describe('lessonKey', () => {
  it('keeps a/b and a__b apart', () => {
    expect(lessonKey('a/b')).not.toBe(lessonKey('a__b'));
  });
});
"""


def _js_repo(tmp: Path, *, runner: str = "vitest") -> tuple[Path, str]:
    repo = tmp / "js"
    _init(repo)
    _write(
        repo,
        {
            "package.json": json.dumps({"type": "module", "devDependencies": {runner: "^3.0.0"}}),
            "package-lock.json": json.dumps({"lockfileVersion": 3, "packages": {}}),
            "src/key.js": KEY_JS,
            "tests/key.test.js": GOOD_TEST.replace("../../src", "../src"),
        },
    )
    return repo, _commit(repo, "lesson keys")


class FakeNodeSandbox:
    name = "fake-node"
    isolation_level = "test"
    supports_node = True

    def __init__(self, cases: list[CaseResult]) -> None:
        self.cases = cases
        self.calls: list[tuple[str, list[str]]] = []

    def run_pytest(self, project_dir, targets, *, timeout_s):  # pragma: no cover - must not run
        raise AssertionError(f"pytest was asked to run {targets}")

    def run_nodetest(self, project_dir, runner, targets, *, timeout_s):
        self.calls.append((runner, list(targets)))
        return ExecResult(["nodetest", runner, *targets], 1, "", "", 0.1, False, self.cases)


def _toolbox(ws: Workspace, sandbox) -> ReviewerToolbox:
    return ReviewerToolbox(
        host=InMemoryHost(fake([])), head=ws, sandbox=sandbox, budget=ReviewBudget()
    )


@pytest.mark.parametrize(
    ("snippet", "why"),
    [
        ("import fs from 'node:fs';", "node:fs"),
        ("import { readFileSync } from 'fs';", "fs"),
        ("const cp = require('child_process');", "child_process"),
        ("import('node:net');", "node:net"),
        ("await fetch('http://x');", "network"),
        ("eval('1');", "eval"),
        ("const t = process.env.TOKEN;", "process"),
        ("const m = await import(name);", "computed"),
    ],
)
def test_js_policy_refuses_escape_hatches(snippet: str, why: str) -> None:
    problem = check_js_test_source(GOOD_TEST + snippet + "\n")
    assert problem is not None and why in problem


def test_js_policy_accepts_a_plain_test_and_needs_a_case() -> None:
    assert check_js_test_source(GOOD_TEST) is None
    assert "no it(" in (check_js_test_source("import { f } from '../../src/key.js';\n") or "")


def test_imports_project_resolves_relative_paths() -> None:
    files = {"src/key.js", "src/lib/index.js", "tests/key.test.js"}
    test = "tests/generated/cr_x.test.js"
    assert imports_project(GOOD_TEST, test, files.__contains__)
    assert imports_project("import { a } from '../../src/lib';", test, files.__contains__)
    assert not imports_project(
        "import { a } from '../../src/missing.js';", test, files.__contains__
    )
    # another test file is not the code under test, and nothing escapes the project
    assert not imports_project("import '../key.test.js';", test, files.__contains__)
    assert not imports_project("import '../../../outside.js';", test, files.__contains__)


def test_parse_report_tells_assertions_from_crashes() -> None:
    report = {
        "testResults": [
            {
                "name": "/work/tests/generated/cr_x.test.js",
                "status": "failed",
                "assertionResults": [
                    {
                        "fullName": "lessonKey keeps apart",
                        "status": "failed",
                        "failureMessages": [
                            "AssertionError: expected 'a__b' not to be 'a__b'\n    at x"
                        ],
                    },
                    {
                        "fullName": "lessonKey crashes",
                        "status": "failed",
                        "failureMessages": ["TypeError: x is not a function"],
                    },
                    {"fullName": "lessonKey ok", "status": "passed", "failureMessages": []},
                ],
            },
            {
                "name": "/work/tests/generated/cr_y.test.js",
                "status": "failed",
                "message": "Failed to load url ../../src/nope.js",
                "assertionResults": [],
            },
        ]
    }
    cases = parse_report(
        json.dumps(report), ["tests/generated/cr_x.test.js", "tests/generated/cr_y.test.js"]
    )
    by_id = {c.nodeid: c for c in cases}
    assert by_id["tests/generated/cr_x.test.js::lessonKey_keeps_apart"].exc_type == "AssertionError"
    assert by_id["tests/generated/cr_x.test.js::lessonKey_crashes"].exc_type == "TypeError"
    assert by_id["tests/generated/cr_x.test.js::lessonKey_ok"].outcome == "passed"
    assert by_id["tests/generated/cr_y.test.js::<collection>"].outcome == "error"
    # jest's matcher errors are plain `Error: expect(...)`
    jest = {
        "testResults": [
            {
                "name": "t.test.js",
                "assertionResults": [
                    {
                        "fullName": "f",
                        "status": "failed",
                        "failureMessages": ["Error: expect(received).toBe(expected)"],
                    }
                ],
            }
        ]
    }
    assert parse_report(json.dumps(jest), ["t.test.js"])[0].exc_type == "AssertionError"


def test_js_test_runs_through_nodetest_and_validates(tmp_path: Path) -> None:
    repo, sha = _js_repo(tmp_path)
    ws = Workspace.export(RepoSource(repo), sha)
    try:
        failing = CaseResult(
            "tests/generated/cr_key.test.js::k", "failed", "call", "AssertionError", "x"
        )
        sbx = FakeNodeSandbox([failing])
        tb = _toolbox(ws, sbx)
        out = tb.write_test(
            WriteTestIn(
                name="key", content=GOOD_TEST, claim_key="c1", rationale="r", language="javascript"
            )
        )
        assert "tests/generated/cr_key.test.js" in out
        test_id = next(iter(tb.written))
        ex = tb.run_generated(test_id)
        assert ex.outcome_on_head == "failed" and ex.reproducible
        assert sbx.calls[0] == ("vitest", ["tests/generated/cr_key.test.js"])
        tb.run_tests(
            RunTestsIn(target="existing")
        )  # the project's own JS suite, generated tests excluded
        assert sbx.calls[-1] == ("vitest", ["tests/key.test.js"])
    finally:
        ws.close()


def test_js_tests_refused_without_node_or_runner(tmp_path: Path) -> None:
    repo, sha = _js_repo(tmp_path, runner="mocha")
    ws = Workspace.export(RepoSource(repo), sha)
    try:
        with pytest.raises(ToolDenied, match="unavailable"):
            _toolbox(ws, FakeNodeSandbox([])).write_test(
                WriteTestIn(
                    name="key",
                    content=GOOD_TEST,
                    claim_key="c1",
                    rationale="r",
                    language="javascript",
                )
            )
    finally:
        ws.close()
    repo2, sha2 = _js_repo(tmp_path / "v")
    ws = Workspace.export(RepoSource(repo2), sha2)
    try:
        no_node = FakeNodeSandbox([])
        no_node.supports_node = False
        with pytest.raises(ToolDenied, match="unavailable"):
            _toolbox(ws, no_node).write_test(
                WriteTestIn(
                    name="key",
                    content=GOOD_TEST,
                    claim_key="c1",
                    rationale="r",
                    language="javascript",
                )
            )
        with pytest.raises(ToolDenied, match="import the code under test"):
            _toolbox(ws, FakeNodeSandbox([])).write_test(
                WriteTestIn(
                    name="key2",
                    content=GOOD_TEST.replace("src/key.js", "src/other.js"),
                    claim_key="c1",
                    rationale="r",
                    language="javascript",
                )
            )
        with pytest.raises(SandboxPolicyError, match="not both"):
            run_targets(
                FakeNodeSandbox([]),
                ws.project_dir,
                ["tests/a.test.js", "tests/test_a.py"],
                timeout_s=5,
            )
    finally:
        ws.close()


@pytest.mark.skipif(
    os.environ.get("RUN_NODE_SANDBOX") != "1" or shutil.which("node") is None,
    reason="real vitest run is opt-in: RUN_NODE_SANDBOX=1 (needs node and the npm registry)",
)
def test_real_vitest_through_shared_local_driver(tmp_path: Path) -> None:
    from code_review.shared_sandbox import SharedSandboxAdapter
    from security_agents.sandbox.driver import LocalProcessDriver

    root = Path(os.environ.get("NODE_SANDBOX_PROJECT", ""))
    if not (root / "package-lock.json").is_file():
        pytest.skip("NODE_SANDBOX_PROJECT must point at a vitest project with a lockfile")
    proj = tmp_path / "p"
    shutil.copytree(root, proj, ignore=shutil.ignore_patterns("node_modules", ".git"))
    (proj / "src").mkdir(exist_ok=True)
    (proj / "src/cr_key.js").write_text(KEY_JS)
    (proj / "tests/generated").mkdir(parents=True, exist_ok=True)
    (proj / "tests/generated/cr_key.test.js").write_text(
        GOOD_TEST.replace("src/key.js", "src/cr_key.js")
    )
    r = run_targets(
        SharedSandboxAdapter(LocalProcessDriver(allow=True)),
        proj,
        ["tests/generated/cr_key.test.js"],
        timeout_s=180,
    )
    # KEY_JS escapes '/' before '_', so 'a/b' -> 'a_5F_5Fb' == lessonKey('a__b'): a real bug
    assert classify(r) == "failed", (r.stdout[-500:], r.stderr[-500:])
    assert [c.exc_type for c in r.cases] == ["AssertionError"]
