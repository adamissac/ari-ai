"""The reviewer's tools. Permissions are enforced here, in code, independent of prompts.

Review mode: read-only repository tools, code-intelligence retrieval, writing *new*
behavioral tests under ``tests/generated/`` and executing pytest in the sandbox.
Repair mode: the same reads plus edits to non-protected source files of the isolated
candidate workspace. Tests, test config, packaging and lockfiles are never writable.
Every execution is stored as an artifact so findings cite executed evidence.
"""

from __future__ import annotations

import ast
import hashlib
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.llm import Tool
from backend.redaction import _PATTERNS as _SECRET_PATTERNS
from code_review.ports import ExecResult, IntelligencePort, ReviewHost, SandboxPort
from code_review.sandbox import SandboxPolicyError, classify
from code_review.workspace import (
    GENERATED_TEST_DIR,
    Workspace,
    WorkspaceError,
    apply_unified_diff,
    diff_target_paths,
    is_denied_read,
    is_protected_path,
    unified_diff,
)
from shared.errors import ErrorCode
from shared.evidence import ArtifactKind, ArtifactRef
from shared.ids import IdPrefix, new_id
from shared.intelligence import (
    BehavioralExpectation,
    ContextPackRequest,
    ContextPurpose,
    SnapshotRef,
)

TOOL_OUTPUT_CAP = 12_000
_FORBIDDEN_IMPORTS = {
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "http",
    "ftplib",
    "smtplib",
    "ctypes",
    "multiprocessing",
    "shutil",
    "asyncio.subprocess",
}
_FORBIDDEN_CALLS = {"system", "popen", "exec", "eval", "fork", "unlink", "rmtree", "__import__"}

_BUDGET_LOCK = threading.Lock()
SEARCH_MAX_FILE_BYTES = 512_000


class ToolDenied(Exception):
    """Raised by a tool handler; the gateway reports it to the model as an error result."""

    code = ErrorCode.TOOL_NOT_ALLOWED


@dataclass
class ReviewBudget:
    max_turns: int = 24
    max_test_runs: int = 14
    max_tests_written: int = 6
    max_edits: int = 8
    max_repair_rounds: int = 3
    test_timeout_s: float = 120.0
    max_diff_chars: int = 40_000


@dataclass
class TestExecution:
    test_id: str
    path: str
    outcome_on_head: str
    reproducible: bool
    report: ArtifactRef
    head_runs: list[ExecResult]
    outcome_on_base: str | None = None
    base_report: ArtifactRef | None = None


@dataclass
class WrittenTest:
    test_id: str
    path: str
    content: str
    claim_key: str
    rationale: str
    artifact: ArtifactRef


# ------------------------------------------------------------------ inputs


class ListFilesIn(BaseModel):
    prefix: str = Field(default="", max_length=300)


class ReadFileIn(BaseModel):
    path: str = Field(max_length=500)
    start_line: int = Field(default=1, ge=1)
    end_line: int | None = Field(default=None, ge=1)


class SearchIn(BaseModel):
    pattern: str = Field(min_length=1, max_length=200, description="Python regular expression")
    path_prefix: str = Field(default="", max_length=300)


class EmptyIn(BaseModel):
    pass


class ContextPackIn(BaseModel):
    focus: list[str] = Field(min_length=1, max_length=8, description="symbols, paths or routes")


class WriteTestIn(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{2,60}$", description="becomes test_cr_<name>.py")
    content: str = Field(min_length=20, max_length=20_000, description="complete pytest module")
    claim_key: str = Field(max_length=32, description="the intent claim this test encodes")
    rationale: str = Field(max_length=500)


class RunTestsIn(BaseModel):
    target: Literal["generated", "existing", "all"] = Field(
        description="'generated' runs one generated test (needs test_id); 'existing' runs the "
        "project's own suite; 'all' runs both"
    )
    test_id: str | None = Field(default=None, pattern=r"^tst_[0-9A-Za-z]{8,64}$")


class EditFileIn(BaseModel):
    path: str = Field(max_length=500)
    old_text: str = Field(min_length=1, max_length=20_000, description="exact unique text")
    new_text: str = Field(max_length=20_000)


class ApplyPatchIn(BaseModel):
    diff: str = Field(min_length=10, max_length=60_000, description="unified diff, a/ b/ paths")


class RevertIn(BaseModel):
    path: str = Field(max_length=500)


# ----------------------------------------------------------------- toolbox


@dataclass
class ReviewerToolbox:
    host: ReviewHost
    head: Workspace
    sandbox: SandboxPort
    budget: ReviewBudget
    change_diff: str = ""
    base: Workspace | None = None
    intelligence: IntelligencePort | None = None
    snapshot_ref: SnapshotRef | None = None
    expectations: dict[str, BehavioralExpectation] = field(default_factory=dict)
    written: dict[str, WrittenTest] = field(default_factory=dict)
    executions: dict[str, TestExecution] = field(default_factory=dict)
    suite_runs: list[tuple[ExecResult, ArtifactRef]] = field(default_factory=list)
    test_runs: int = 0
    edits: int = 0
    pristine: Workspace | None = None  # repair mode: head before any edit
    protected_digests: dict[str, str] = field(default_factory=dict)

    # -------------------------------------------------------------- reads
    def list_files(self, a: ListFilesIn) -> str:
        files = [f for f in self.head.files() if f.startswith(a.prefix) and not is_denied_read(f)]
        return "\n".join(files[:500]) or "(no files)"

    def read_file(self, a: ReadFileIn) -> str:
        try:
            lines = self.head.read(a.path).splitlines()
        except WorkspaceError as e:
            raise ToolDenied(str(e)) from e
        end = min(a.end_line or len(lines), len(lines), a.start_line + 400)
        body = "\n".join(f"{i:5d}  {lines[i - 1]}" for i in range(a.start_line, end + 1))
        header = f"# {a.path} @ {self.head.commit_sha[:12]} lines {a.start_line}-{end} of {len(lines)} (untrusted data)\n"
        return (header + body)[:TOOL_OUTPUT_CAP]

    def search_code(self, a: SearchIn) -> str:
        try:
            rx = re.compile(a.pattern)
        except re.error as e:
            raise ToolDenied(f"invalid regex: {e}") from e
        hits: list[str] = []
        skipped = 0
        for rel in self.head.files():
            if not rel.startswith(a.path_prefix) or is_denied_read(rel):
                continue
            try:
                # Data dumps and logs, not code: reading them made each search take seconds.
                if self.head.path(rel).stat().st_size > SEARCH_MAX_FILE_BYTES:
                    skipped += 1
                    continue
                text = self.head.read(rel)
            except (WorkspaceError, OSError):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{rel}:{n}: {line.strip()[:200]}")
                    if len(hits) >= 200:
                        return "\n".join(hits) + "\n(truncated at 200 matches)"
        note = (
            f"\n(skipped {skipped} file(s) over {SEARCH_MAX_FILE_BYTES // 1000} KB)"
            if skipped
            else ""
        )
        return ("\n".join(hits) or "(no matches)") + note

    def get_change_diff(self, _: EmptyIn) -> str:
        if not self.change_diff:
            return "No base commit: this is a full-snapshot review (no diff available)."
        d = self.change_diff
        cap = self.budget.max_diff_chars
        return d if len(d) <= cap else d[:cap] + f"\n... (diff truncated at {cap} chars)"

    def list_expectations(self, _: EmptyIn) -> str:
        if self.intelligence is None or self.snapshot_ref is None:
            return (
                "UNAVAILABLE: code-intelligence service is not connected for this run. "
                "No expectations are known from the index; derive intent from docs, "
                "docstrings, tests and the change text, and label it honestly."
            )
        return (
            "\n".join(
                f"{e.id} [{e.status.value}/{e.kind.value} conf={e.confidence}] {e.subject_ref}: {e.statement}"
                for e in self.expectations.values()
            )
            or "(index has no expectations for this snapshot)"
        )

    def get_context_pack(self, a: ContextPackIn) -> str:
        if self.intelligence is None or self.snapshot_ref is None:
            return "UNAVAILABLE: code-intelligence service is not connected; use read_file/search_code."
        pack = self.intelligence.build_context_pack(
            ContextPackRequest(
                snapshot_ref=self.snapshot_ref,
                purpose=ContextPurpose.review,
                focus=a.focus,
                token_budget=8000,
            )
        )
        parts = [f"context pack {pack.id} ({pack.token_count} tokens, untrusted data)"]
        for ch in pack.chunks:
            p = ch.provenance
            loc = f"{p.path}:{p.span.start_line}-{p.span.end_line}" if p.path and p.span else p.kind
            parts.append(f"--- {loc} {p.symbol or ''}\n{ch.content}")
        return "\n".join(parts)[:TOOL_OUTPUT_CAP]

    # ------------------------------------------------------- test writing
    def write_test(self, a: WriteTestIn) -> str:
        if len(self.written) >= self.budget.max_tests_written:
            raise ToolDenied(f"test budget exhausted ({self.budget.max_tests_written} tests)")
        problem = check_test_source(a.content)
        if problem:
            raise ToolDenied(problem)
        unknown = [v for v in credential_values(a.content) if not self._in_repo(v)]
        if unknown:
            raise ToolDenied(
                "generated tests may only use credential-shaped values that already exist in the "
                "repository's own fixtures"
            )
        rel = self.head.repo_rel(f"{GENERATED_TEST_DIR}/test_cr_{a.name}.py")
        if self.head.exists(rel):
            raise ToolDenied(f"{rel} already exists; choose another name")
        self.head.write(rel, a.content)
        init = self.head.repo_rel(f"{GENERATED_TEST_DIR}/__init__.py")
        if self.head.exists(self.head.repo_rel("tests/__init__.py")) and not self.head.exists(init):
            self.head.write(init, "")
        if self.base is not None:
            self.base.write(rel, a.content)
            if self.head.exists(init) and not self.base.exists(init):
                self.base.write(init, "")
        test_id = new_id(IdPrefix.tst)
        art = self.host.store_text(a.content, ArtifactKind.other, media_type="text/x-python")
        self.written[test_id] = WrittenTest(test_id, rel, a.content, a.claim_key, a.rationale, art)
        return f"wrote {rel} as test_id={test_id}. Run it with run_tests(target='generated', test_id='{test_id}')."

    def _in_repo(self, value: str) -> bool:
        for rel in self.head.files():
            if is_denied_read(rel) or GENERATED_TEST_DIR in rel:
                continue
            try:
                if value in self.head.read(rel):
                    return True
            except WorkspaceError:
                continue
        return False

    # ------------------------------------------------------- execution
    def _charge_test_run(self) -> None:
        with _BUDGET_LOCK:  # run_generated and parallel run_tests calls charge from threads
            if self.test_runs >= self.budget.max_test_runs:
                raise ToolDenied(f"test-run budget exhausted ({self.budget.max_test_runs} runs)")
            self.test_runs += 1

    def _exec(self, ws: Workspace, targets: list[str], *, speculative: bool = False) -> ExecResult:
        # A speculative run is charged only when its result is used (see run_generated).
        if not speculative:
            self._charge_test_run()
        try:
            return self.sandbox.run_pytest(
                ws.project_dir, targets, timeout_s=self.budget.test_timeout_s
            )
        except SandboxPolicyError as e:
            raise ToolDenied(str(e)) from e

    def _existing_targets(self, ws: Workspace) -> list[str]:
        gen = f"{GENERATED_TEST_DIR}/"
        tests = [
            ws.project_rel(f)
            for f in ws.files()
            if f.endswith(".py")
            and ws.project_rel(f).startswith(("tests/", "test/"))
            and not ws.project_rel(f).startswith(gen)
            and (f.rsplit("/", 1)[-1].startswith("test_") or f.endswith("_test.py"))
        ]
        return sorted(tests)

    def _store_run(self, label: str, ws: Workspace, results: list[ExecResult]) -> ArtifactRef:
        return self.host.store_json(
            {
                "label": label,
                "commit_sha": ws.commit_sha,
                "runs": [r.to_json() for r in results],
                "classification": [classify(r) for r in results],
            },
            ArtifactKind.test_report,
        )

    def run_generated(self, test_id: str) -> TestExecution:
        wt = self.written.get(test_id)
        if wt is None:
            raise ToolDenied(f"unknown test_id {test_id}; write it with write_test first")
        target = [self.head.project_rel(wt.path)]
        # Head, its repeat and the base run are independent sandboxes: start all three at
        # once and keep the repeat/base only when the head outcome calls for them.
        with ThreadPoolExecutor(max_workers=3) as pool:
            head = pool.submit(self._exec, self.head, target)
            repeat = pool.submit(self._exec, self.head, target, speculative=True)
            on_base = (
                pool.submit(self._exec, self.base, target, speculative=True)
                if self.base is not None
                else None
            )
            first = head.result()
            runs = [first]
            outcome = classify(first)
            reproducible = True
            second = repeat.result()
            if outcome == "failed":  # a failure only counts if it reproduces identically
                self._charge_test_run()
                runs.append(second)
                reproducible = classify(second) == "failed" and {
                    (c.nodeid, c.outcome) for c in second.cases
                } == {(c.nodeid, c.outcome) for c in first.cases}
            base_run = None
            if on_base is not None:
                speculative_base = on_base.result()
                if outcome in ("failed", "passed"):
                    self._charge_test_run()
                    base_run = speculative_base
        report = self._store_run(f"generated:{test_id}@head", self.head, runs)
        ex = TestExecution(test_id, wt.path, outcome, reproducible, report, runs)
        if base_run is not None and self.base is not None:
            ex.outcome_on_base = classify(base_run)
            ex.base_report = self._store_run(f"generated:{test_id}@base", self.base, [base_run])
        self.executions[test_id] = ex
        return ex

    def run_tests(self, a: RunTestsIn) -> str:
        lines: list[str] = []
        if a.target in ("generated", "all"):
            ids = [a.test_id] if a.test_id else list(self.written)
            if not ids:
                raise ToolDenied("no generated tests yet; call write_test first")
            for tid in ids:
                ex = self.run_generated(tid)
                last = ex.head_runs[-1]
                lines.append(
                    f"[{tid}] {ex.path}: outcome_on_head={ex.outcome_on_head}"
                    f" reproducible={ex.reproducible} exit={last.exit_code}"
                    + (f" outcome_on_base={ex.outcome_on_base}" if ex.outcome_on_base else "")
                    + f" report_artifact={ex.report.id}"
                )
                lines.extend(_case_lines(last))
                lines.append(_tail(last.stdout, 2500))
        if a.target in ("existing", "all"):
            targets = self._existing_targets(self.head)
            if not targets:
                lines.append("existing suite: no test files found")
            else:
                res = self._exec(self.head, targets)
                art = self._store_run("existing@head", self.head, [res])
                self.suite_runs.append((res, art))
                lines.append(
                    f"existing suite: {classify(res)} exit={res.exit_code} "
                    f"({sum(c.outcome == 'passed' for c in res.cases)} passed, "
                    f"{sum(c.outcome in ('failed', 'error') for c in res.cases)} failed/error) "
                    f"report_artifact={art.id}"
                )
                lines.extend(_case_lines(res, only_failing=True))
                lines.append(_tail(res.stdout, 2500))
        return "\n".join(lines)[:TOOL_OUTPUT_CAP]

    # ------------------------------------------------------- repair edits
    def _check_writable(self, rel: str) -> str:
        try:
            rel = self.head.path(rel).relative_to(self.head.root).as_posix()
        except WorkspaceError as e:
            raise ToolDenied(str(e)) from e
        if is_protected_path(rel):
            raise ToolDenied(
                f"{rel} is protected (tests, test config, packaging, lockfiles); "
                "repairs may only change implementation files"
            )
        if is_denied_read(rel):
            raise ToolDenied(f"{rel} is not writable")
        return rel

    def _count_edit(self) -> None:
        if self.edits >= self.budget.max_edits:
            raise ToolDenied(f"edit budget exhausted ({self.budget.max_edits} edits)")
        self.edits += 1

    def edit_file(self, a: EditFileIn) -> str:
        rel = self._check_writable(a.path)
        try:
            text = self.head.read(rel)
        except WorkspaceError as e:
            raise ToolDenied(str(e)) from e
        count = text.count(a.old_text)
        if count != 1:
            raise ToolDenied(f"old_text must match exactly once in {rel} (found {count})")
        self._count_edit()
        self.head.write(rel, text.replace(a.old_text, a.new_text, 1))
        return f"edited {rel}. Re-run tests to check the change."

    def apply_patch(self, a: ApplyPatchIn) -> str:
        try:
            paths = diff_target_paths(a.diff)
        except WorkspaceError as e:
            raise ToolDenied(str(e)) from e
        if not paths:
            raise ToolDenied("diff names no files")
        for p in paths:
            self._check_writable(p)
        self._count_edit()
        ok, msg = apply_unified_diff(self.head, a.diff)
        if not ok:
            raise ToolDenied(f"patch did not apply: {msg}")
        return f"applied patch to {', '.join(paths)}"

    def show_diff(self, _: EmptyIn) -> str:
        if self.pristine is None:
            raise ToolDenied("show_diff is only available in repair mode")
        diff, _changed = unified_diff(self.pristine, self.head)
        return (diff or "(no changes)")[:TOOL_OUTPUT_CAP]

    def revert_file(self, a: RevertIn) -> str:
        if self.pristine is None:
            raise ToolDenied("revert_file is only available in repair mode")
        rel = self._check_writable(a.path)
        if self.pristine.exists(rel):
            self.head.write(rel, self.pristine.read(rel))
        elif self.head.exists(rel):
            self.head.path(rel).unlink()
        return f"reverted {rel}"

    # -------------------------------------------------------- tool lists
    def _read_tools(self) -> list[Tool[Any]]:
        return [
            Tool(
                "list_files",
                "List repository files at the pinned commit.",
                ListFilesIn,
                self.list_files,
                parallel_safe=True,
            ),
            Tool(
                "read_file",
                "Read a file at the pinned commit with line numbers (cite these line numbers).",
                ReadFileIn,
                self.read_file,
                parallel_safe=True,
            ),
            Tool(
                "search_code",
                "Regex search over the pinned repository.",
                SearchIn,
                self.search_code,
                parallel_safe=True,
            ),
            Tool(
                "list_expectations",
                "Behavioral expectations from the code-intelligence index for this snapshot.",
                EmptyIn,
                self.list_expectations,
                parallel_safe=True,
            ),
            Tool(
                "get_context_pack",
                "Retrieve a SHA-pinned context pack (callers, callees, tests) for symbols/paths.",
                ContextPackIn,
                self.get_context_pack,
                parallel_safe=True,
            ),
        ]

    def review_tools(self) -> list[Tool[Any]]:
        return [
            *self._read_tools(),
            Tool(
                "get_change_diff",
                "The unified diff of the change under review (base..head).",
                EmptyIn,
                self.get_change_diff,
                parallel_safe=True,
            ),
            Tool(
                "write_test",
                "Write a NEW pytest module under tests/generated/ that passes iff the claimed "
                "intended behavior holds. Returns a test_id.",
                WriteTestIn,
                self.write_test,
            ),
            Tool(
                "run_tests",
                "Execute tests in the sandbox and return real outcomes (failed = assertion "
                "failure; error = harness/tooling problem).",
                RunTestsIn,
                lambda a: self.run_tests(a),
                parallel_safe=True,  # each run is its own sandbox; writes stay sequential
            ),
        ]

    def repair_tools(self) -> list[Tool[Any]]:
        return [
            *self._read_tools(),
            Tool(
                "edit_file",
                "Replace one exact, unique text span in an implementation file of the "
                "candidate workspace.",
                EditFileIn,
                self.edit_file,
            ),
            Tool(
                "apply_patch",
                "Apply a unified diff to implementation files.",
                ApplyPatchIn,
                self.apply_patch,
            ),
            Tool("show_diff", "Show the candidate diff so far.", EmptyIn, self.show_diff),
            Tool(
                "revert_file", "Revert one file to the pinned commit.", RevertIn, self.revert_file
            ),
            Tool(
                "run_tests",
                "Execute the failing generated test and/or the existing suite against the candidate.",
                RunTestsIn,
                lambda a: self.run_tests(a),
            ),
        ]


def check_test_source(content: str) -> str | None:
    """Static policy for generated tests: valid Python, has a test, no process/network/fs abuse."""
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return f"test does not parse: {e}"
    has_test = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            has_test = True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if (
                    alias.name.split(".")[0] in _FORBIDDEN_IMPORTS
                    or alias.name in _FORBIDDEN_IMPORTS
                ):
                    return f"generated tests may not import {alias.name}"
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in _FORBIDDEN_IMPORTS:
                return f"generated tests may not import from {node.module}"
        if isinstance(node, ast.Call):
            fn = node.func
            name = (
                fn.attr
                if isinstance(fn, ast.Attribute)
                else fn.id
                if isinstance(fn, ast.Name)
                else ""
            )
            if name in _FORBIDDEN_CALLS or name.startswith(("execv", "execl", "spawn")):
                return f"generated tests may not call {name}()"
    if not has_test:
        return "module defines no test_* function"
    return None


def credential_values(text: str) -> list[str]:
    """Substrings the backend redactor would scrub (same patterns, single source)."""
    return [m.group(0) for pattern, _ in _SECRET_PATTERNS for m in pattern.finditer(text)]


def _case_lines(r: ExecResult, *, only_failing: bool = False) -> list[str]:
    out = []
    for c in r.cases:
        if only_failing and c.outcome not in ("failed", "error"):
            continue
        msg = f" {c.exc_type}: {c.message[:300]}" if c.outcome in ("failed", "error") else ""
        out.append(f"  - {c.nodeid} [{c.phase}] {c.outcome}{msg}")
    return out[:40]


def _tail(text: str, n: int) -> str:
    return ("...stdout tail:\n" + text[-n:]) if text.strip() else ""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
