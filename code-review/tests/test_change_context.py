"""The reviewer's deterministic first-turn context and JS comment intent (no model calls)."""

from __future__ import annotations

from pathlib import Path

from cr_fakes import InMemoryHost, fake, make_request
from cr_scenarios import Scenario, _commit, _init, _write, line_of

from code_review.context import change_context, hunk_citations
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


def test_hunk_citations_cover_the_head_side_of_each_cited_files_hunks(tmp_path: Path) -> None:
    sc = _js_repo(tmp_path)
    assert sc.base_sha
    diff = git_diff(RepoSource(sc.repo), sc.base_sha, sc.head_sha)
    cited = [CitationIn(source_kind=SourceKind.code, path="src/summary.js", start_line=9)]
    (c,) = hunk_citations(diff, cited)
    assert (c.path, c.start_line) == ("src/summary.js", 1)
    assert c.end_line == SUMMARY_HEAD.count("\n") and not c.quote
    assert hunk_citations(diff, [CitationIn(source_kind=SourceKind.code, path="x.js")]) == []


def test_commit_message_quotes_are_accepted_but_never_confirm(tmp_path: Path) -> None:
    """Production gt2/py-contract: the claim quoted the commit message, which the checker did
    not know, so the claim was rejected."""
    from cr_fakes import call

    from code_review.agent import ReviewerAgentRunner

    sc = _js_repo(tmp_path)
    claim = {
        "key": "c_rename",
        "statement": "The change only renames a field.",
        "proposed_status": "confirmed",
        "citations": [{"source_kind": "change_intent", "quote": "Rename the passed count field"}],
    }
    host = InMemoryHost(fake([call("submit_result", summary="s", claims=[claim], findings=[])]))
    outcome = ReviewerAgentRunner(host, RepoSource(sc.repo)).review(make_request(host, sc))
    assert not any("c_rename" in r for r in outcome.rejected), outcome.rejected
    (c,) = outcome.result.intent_evidence.claims
    assert c.status.value == "inferred"


def test_a_test_cited_by_name_without_a_line_resolves_to_its_def(tmp_path: Path) -> None:
    """Production gt3/py-contract: the model cited tests/test_api.py and the failing test's name
    but no line, so the only confirming citation was rejected."""
    from cr_scenarios import INVOICE_TESTS_HEAD, discount_rounding

    sc = discount_rounding(tmp_path)
    ws = Workspace.export(RepoSource(sc.repo), sc.head_sha)
    try:
        checker = CitationChecker(ws, make_request(InMemoryHost(fake([])), sc).change_intent, {})
        ev, kind, note = checker.check(
            CitationIn(
                source_kind=SourceKind.test,
                path="tests/test_invoice.py",
                quote="test_line_total_rounds_half_up expects 0.13",
            )
        )
        assert ev is not None and kind is SourceKind.test, note
        line = line_of(INVOICE_TESTS_HEAD, "def test_line_total_rounds_half_up")
        assert ev.span is not None and ev.span.start_line == line
        missing = CitationIn(source_kind=SourceKind.test, path="tests/test_invoice.py", quote="x")
        assert checker.check(missing)[0] is None
    finally:
        ws.close()


def test_a_paraphrased_test_quote_resolves_to_the_test_it_names(tmp_path: Path) -> None:
    """Live gtB2 py-float/py-rename: the citation had lines and a paraphrase naming the test
    ("test_x asserts 201"); the quote check rejected it, so the rule was never confirmed."""
    from cr_scenarios import INVOICE_TESTS_HEAD, discount_rounding

    sc = discount_rounding(tmp_path)
    ws = Workspace.export(RepoSource(sc.repo), sc.head_sha)
    try:
        checker = CitationChecker(ws, make_request(InMemoryHost(fake([])), sc).change_intent, {})
        line = line_of(INVOICE_TESTS_HEAD, "def test_line_total_rounds_half_up")
        ev, kind, note = checker.check(
            CitationIn(
                source_kind=SourceKind.test,
                path="tests/test_invoice.py",
                start_line=line,
                end_line=line + 1,
                quote="test_line_total_rounds_half_up asserts 0.13",
            )
        )
        assert ev is not None and kind is SourceKind.test, note
        assert ev.span is not None and ev.span.start_line == line
        # a paraphrase in a code citation is still rejected
        bad = CitationIn(
            source_kind=SourceKind.code,
            path="tests/test_invoice.py",
            start_line=line,
            quote="test_line_total_rounds_half_up asserts 0.13",
        )
        assert checker.check(bad)[0] is None
    finally:
        ws.close()


def test_overlong_model_text_is_clipped_not_rejected() -> None:
    """Live gtB2 js-lessonkey: a 530-character summary failed validation three times and
    the whole review was lost."""
    from code_review.models import ReviewerReport

    report = ReviewerReport.model_validate({"summary": "x" * 530, "claims": [], "findings": []})
    assert report.summary == "x" * 500


def test_quotes_wrapped_across_comment_lines_are_found() -> None:
    """Live gtB3 js-batch-obo: the quoted sentence spans `//` and ` * ` comment lines."""
    from code_review.intent import locate_quote

    lines = [
        "  for (const row of roster) {",
        "    // The roster row goes last, so a failure above leaves the student still",
        "    // reachable to try again rather than orphaning their records.",
        "/**",
        " * The rules let a teacher clear an archived class's records once they are",
        " * past the stated year, and nothing wider than that. */",
    ]
    q1 = "The roster row goes last, so a failure above leaves the student still reachable"
    assert locate_quote(q1, lines, 2, 3) == (2, 3)
    q2 = "The rules let a teacher clear an archived class's records once they are past"
    assert locate_quote(q2, lines, 5, 6) == (5, 6)
    assert locate_quote("The roster row goes first", lines, 2, 3) is None


def test_a_js_test_title_in_the_quote_resolves_to_its_it_block(tmp_path: Path) -> None:
    """Live gtB3 js-foreach-async: 'skips assignments that were archived in the source
    class: if (a.archived) continue' named a vitest `it(...)` title."""
    sc = _js_repo(tmp_path)
    _write(
        sc.repo,
        {
            "tests/roll.test.js": "describe('roll', () => {\n"
            "  it('skips assignments that were archived in the source class', () => {\n"
            "    expect(1).toBe(1);\n  });\n});\n"
        },
    )
    head = _commit(sc.repo, "add test")
    ws = Workspace.export(RepoSource(sc.repo), head)
    try:
        checker = CitationChecker(ws, make_request(InMemoryHost(fake([])), sc).change_intent, {})
        ev, kind, note = checker.check(
            CitationIn(
                source_kind=SourceKind.test,
                path="tests/roll.test.js",
                start_line=1,
                end_line=1,
                quote="skips assignments that were archived in the source class: if (a.archived)",
            )
        )
        assert ev is not None and kind is SourceKind.test, note
        assert ev.span is not None and ev.span.start_line == 2
    finally:
        ws.close()
