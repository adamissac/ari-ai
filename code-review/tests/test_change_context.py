"""The reviewer's deterministic first-turn context and JS comment intent (no model calls)."""

from __future__ import annotations

from pathlib import Path

from cr_fakes import InMemoryHost, fake, make_request
from cr_scenarios import Scenario, _commit, _init, _write, line_of

from code_review.context import change_context
from code_review.intent import CitationChecker
from code_review.models import CitationIn, SourceKind
from code_review.ports import RepoSource
from code_review.workspace import (
    Workspace,
    changed_paths_between,
    comment_ranges,
    commit_messages,
    git_diff,
)

SUMMARY_BASE = """/* Summary of unit scores.
   Unit numbers are 1..10 inclusive. */
export function summarize(scores) {
  return { scores: scores, passed: Object.keys(scores).length };
}
"""
SUMMARY_HEAD = SUMMARY_BASE.replace("passed:", "passedCount:")
CALLER = """import { summarize } from './summary.js';

export function render(scores) {
  // the badge shows how many units passed
  return summarize(scores).passed + ' passed';
}
"""
TEST = "import { summarize } from '../src/summary.js';\ntest('x', () => summarize({}));\n"


def _js_repo(tmp: Path) -> Scenario:
    repo = tmp / "js-repo"
    _init(repo)
    _write(repo, {"src/summary.js": SUMMARY_BASE, "src/page.js": CALLER, "tests/s.test.js": TEST})
    base = _commit(repo, "summary module")
    _write(repo, {"src/summary.js": SUMMARY_HEAD})
    head = _commit(repo, "Rename the passed count field")
    return Scenario(repo=repo, base_sha=base, head_sha=head, title="push", body="")


def test_change_context_lists_callers_the_diff_never_touched(tmp_path: Path) -> None:
    sc = _js_repo(tmp_path)
    source = RepoSource(sc.repo)
    assert sc.base_sha
    diff = git_diff(source, sc.base_sha, sc.head_sha)
    ws = Workspace.export(source, sc.head_sha)
    try:
        ctx = change_context(ws, diff, changed_paths_between(source, sc.base_sha, sc.head_sha))
    finally:
        ws.close()
    page = line_of(CALLER, "summarize(scores).passed")
    assert "references to changed symbol `summarize`:" in ctx
    assert f"src/page.js:{page}: return summarize(scores).passed + ' passed';" in ctx
    # the renamed field is still read by the caller; a comment mentioning it is not a use
    assert "`passed` was removed from changed lines; other uses to re-check:" in ctx
    assert "src/page.js:4:" not in ctx
    assert "tests mentioning the changed code: tests/s.test.js" in ctx
    assert commit_messages(source, sc.base_sha, sc.head_sha).strip() == (
        "Rename the passed count field"
    )
    assert change_context(ws, "", []) == ""


def test_js_comment_blocks_count_as_docstrings_and_code_lines_do_not(tmp_path: Path) -> None:
    assert comment_ranges("a(); // tail\n// one\n// two\nf();\n/* x\n * y */\n/** d */ g();\n") == [
        (2, 3),
        (5, 6),
    ]
    sc = _js_repo(tmp_path)
    source = RepoSource(sc.repo)
    ws = Workspace.export(source, sc.head_sha)
    try:
        host = InMemoryHost(fake([]))
        checker = CitationChecker(ws, make_request(host, sc).change_intent, {})

        def kind(start: int, quote: str) -> SourceKind:
            ev, k, note = checker.check(
                CitationIn(
                    source_kind="docstring",
                    path="src/summary.js",
                    start_line=start,
                    end_line=start,
                    quote=quote,
                )
            )
            assert ev is not None, note
            return k

        assert kind(2, "Unit numbers are 1..10 inclusive.") is SourceKind.docstring
        assert kind(3, "export function summarize(scores) {") is SourceKind.code
    finally:
        ws.close()
