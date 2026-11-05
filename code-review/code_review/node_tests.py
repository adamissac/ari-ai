"""JavaScript tests for the reviewer: the project's own vitest/jest, run in the sandbox.

The command is still fixed: the security_agents sandbox ``nodetest`` mode runs
``node node_modules/<runner>`` with a JSON reporter, never anything model-authored. The
generated test itself is policed statically here (no process, network or filesystem
access; it must import the code under test from the repository), as Python tests are.
"""

from __future__ import annotations

import json
import posixpath
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from code_review.ports import CaseResult

JS_TEST_SUFFIXES = (".test.js", ".test.mjs", ".test.cjs", ".spec.js", ".spec.mjs", ".spec.cjs")
RUNNERS = ("vitest", "jest")
_SOURCE_SUFFIXES = (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx")

_FORBIDDEN_MODULES = {
    "child_process",
    "cluster",
    "dgram",
    "dns",
    "fs",
    "fs/promises",
    "http",
    "http2",
    "https",
    "inspector",
    "module",
    "net",
    "os",
    "tls",
    "vm",
    "worker_threads",
}
_SPECIFIER = re.compile(
    r"""(?:\bimport\s*(?:[\w${}\s,*]+?\s*from\s*)?|\bexport\s*[\w${}\s,*]*?\s*from\s*|"""
    r"""\brequire\s*\(\s*|\bimport\s*\(\s*)(['"`])([^'"`]+)\1"""
)
_FORBIDDEN_CODE = (
    (re.compile(r"\beval\s*\("), "eval()"),
    (re.compile(r"\bnew\s+Function\b|\bFunction\s*\("), "Function()"),
    (re.compile(r"\bprocess\s*\.\s*(env|exit|kill|binding|dlopen)\b"), "process internals"),
    (re.compile(r"\b(fetch|XMLHttpRequest|WebSocket)\b"), "network access"),
    (re.compile(r"\bimport\s*\(\s*[^'\"`\s]"), "a computed dynamic import"),
    (re.compile(r"\brequire\s*\(\s*[^'\"`\s]"), "a computed require"),
)
_HAS_TEST = re.compile(r"\b(it|test)(\.each\([^)]*\))?\s*\(\s*['\"`]")
_ERROR_HEAD = re.compile(r"^\s*([A-Za-z_$][\w$.]*)\s*:")


def is_js_test(target: str) -> bool:
    return target.split("::", 1)[0].endswith(JS_TEST_SUFFIXES)


def node_runner(project_dir: Path) -> str | None:
    """The project's own test runner, when it is installable from its lockfile."""
    pkg, lock = project_dir / "package.json", project_dir / "package-lock.json"
    if not (pkg.is_file() and lock.is_file()):
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
    return next((r for r in RUNNERS if r in deps), None)


def runner_args(runner: str, targets: Sequence[str]) -> list[str]:
    files = [t.split("::", 1)[0] for t in targets]
    # two workers: a jsdom suite on more was OOM-killed (exit 137) in the 2 GB microVM
    if runner == "vitest":
        return [runner, "run", "--maxWorkers=2", "--minWorkers=1", *files]
    return [runner, "--ci", "--maxWorkers=2", *files]


def check_js_test_source(content: str) -> str | None:
    """Static policy for a generated JS test: has a test, no process/network/fs access."""
    if not _HAS_TEST.search(content):
        return "module defines no it('...') / test('...') case"
    for _, spec in _SPECIFIER.findall(content):
        bare = spec.removeprefix("node:")
        if bare in _FORBIDDEN_MODULES or bare.split("/", 1)[0] in _FORBIDDEN_MODULES:
            return f"generated tests may not import {spec}"
    for pattern, what in _FORBIDDEN_CODE:
        if pattern.search(content):
            return f"generated tests may not use {what}"
    return None


def imports_project(content: str, test_rel: str, exists: Callable[[str], bool]) -> bool:
    """Does the test import a source module of the repository (by a relative path)?

    `test_rel` and `exists` work in project-relative posix paths."""
    base = posixpath.dirname(test_rel)
    for _, spec in _SPECIFIER.findall(content):
        if not spec.startswith("."):
            continue
        rel = posixpath.normpath(posixpath.join(base, spec))
        if rel.startswith("../"):
            continue
        candidates = (
            [rel] if rel.endswith(_SOURCE_SUFFIXES) else [rel + s for s in _SOURCE_SUFFIXES]
        )
        if not rel.endswith(_SOURCE_SUFFIXES):
            candidates += [f"{rel}/index{s}" for s in _SOURCE_SUFFIXES]
        if any(exists(c) and not c.endswith(JS_TEST_SUFFIXES) for c in candidates):
            return True
    return False


def _exc_type(messages: Sequence[str]) -> str:
    first = (messages[0] if messages else "").strip().splitlines()
    head = first[0] if first else ""
    m = _ERROR_HEAD.match(head)
    name = m.group(1).rsplit(".", 1)[-1] if m else "Error"
    # jest's matchers throw a plain Error whose message starts with `expect(`
    if name == "Error" and "expect(" in head:
        return "AssertionError"
    return name


def parse_report(raw: bytes | str | None, targets: Sequence[str]) -> list[CaseResult]:
    """vitest/jest JSON report -> the reviewer's case records, nodeids `<file>::<title>`."""
    if not raw:
        return []
    try:
        data: dict[str, Any] = json.loads(raw)
    except ValueError:
        return []
    files = [t.split("::", 1)[0] for t in targets]
    cases: list[CaseResult] = []
    for suite in data.get("testResults") or []:
        name = str(suite.get("name", ""))
        rel = next((f for f in files if name == f or name.endswith("/" + f)), name)
        results = suite.get("assertionResults") or []
        if suite.get("status") == "failed" and not results:
            message = str(suite.get("message") or suite.get("failureMessage") or "")
            cases.append(
                CaseResult(
                    rel + "::<collection>", "error", "collect", "CollectionError", message[-800:]
                )
            )
            continue
        for case in results:
            title = "_".join(str(case.get("fullName") or case.get("title") or "").split())
            status = str(case.get("status"))
            messages = [str(m) for m in case.get("failureMessages") or []]
            if status == "failed":
                cases.append(
                    CaseResult(
                        f"{rel}::{title}",
                        "failed",
                        "call",
                        _exc_type(messages),
                        "\n".join(messages)[:800],
                    )
                )
            else:
                cases.append(
                    CaseResult(
                        f"{rel}::{title}", "passed" if status == "passed" else "skipped", "call"
                    )
                )
    return cases
