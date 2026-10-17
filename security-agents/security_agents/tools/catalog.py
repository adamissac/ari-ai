"""Tool implementations (docs/agents/TOOL_REGISTRY.md catalog).

There is deliberately no generic shell, HTTP client or filesystem tool. Each
handler takes typed arguments, resolves paths under the snapshot/worktree root,
and returns a compact JSON payload with citations the agent can quote.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Literal

from pydantic import Field

from ..checks.library import CheckLibrary
from ..contracts import StrictModel
from ..intel import CodeIntel, FindingsHistory
from ..sandbox.workspace import safe_rel_path
from .registry import ToolContext, ToolDef, ToolRegistry

# --------------------------------------------------------------------------- args


class ReadSpanArgs(StrictModel):
    path: str = Field(description="Repository-relative file path from the snapshot.")
    start_line: int = Field(ge=1, description="First line to read (1-based).")
    end_line: int = Field(ge=1, description="Last line to read; at most 400 lines are returned.")


class SearchArgs(StrictModel):
    pattern: str = Field(min_length=2, max_length=200, description="Python regular expression.")
    max_results: int = Field(default=20, ge=1, le=50)


class NeighborsArgs(StrictModel):
    symbol: str = Field(min_length=1, max_length=200, description="Qualified or bare symbol name.")


class ExpectationsArgs(StrictModel):
    subject: str | None = Field(
        default=None, max_length=200, description="File path or symbol to filter expectations by."
    )


class HistoryArgs(StrictModel):
    subject: str | None = Field(default=None, max_length=200)


class StaticAnalyzeArgs(StrictModel):
    path: str = Field(description="Python file to analyse, repository-relative.")


class ListTemplatesArgs(StrictModel):
    category: str | None = Field(default=None, max_length=100)


class RunTemplateArgs(StrictModel):
    template_ref: str = Field(
        max_length=120,
        description="Template reference as `category.name@version` from checks.list_templates.",
    )
    target_id: str = Field(max_length=120, description="Target id from the authorized scope.")
    parameters: dict[str, str | int] = Field(
        default_factory=dict, description="Typed parameters declared by the template."
    )


class WriteFileArgs(StrictModel):
    path: str = Field(description="Worktree-relative path to write.")
    content: str = Field(max_length=60_000, description="Full new file content.")


class DiffArgs(StrictModel):
    pass


class TestsRunArgs(StrictModel):
    selection: Literal["project_suite", "added_tests"] = Field(
        default="project_suite", description="Which tests to run in the sandbox."
    )
    node_ids: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Optional pytest node ids (repository-relative) to narrow the run.",
    )


class ApplyFreshArgs(StrictModel):
    patch_id: str = Field(max_length=120, description="Patch candidate id handed to this Verify step.")


# --------------------------------------------------------------------------- handlers


def _intel(ctx: ToolContext) -> CodeIntel:
    return ctx.service("intel")


def h_read_span(ctx: ToolContext, args: ReadSpanArgs) -> dict[str, Any]:
    span = _intel(ctx).read_span(args.path, args.start_line, args.end_line)
    return {
        "path": span.path,
        "start_line": span.start_line,
        "end_line": span.end_line,
        "sha": _intel(ctx).snapshot.commit_sha,
        "content": span.content,
    }


def h_search(ctx: ToolContext, args: SearchArgs) -> dict[str, Any]:
    try:
        hits = _intel(ctx).search(args.pattern, max_results=args.max_results)
    except ValueError as exc:
        return {"error": "BAD_PATTERN", "detail": str(exc)[:200]}
    return {"pattern": args.pattern, "count": len(hits), "hits": hits}


def h_neighbors(ctx: ToolContext, args: NeighborsArgs) -> dict[str, Any]:
    return {"query": args.symbol, **_intel(ctx).neighbors(args.symbol)}


def h_expectations(ctx: ToolContext, args: ExpectationsArgs) -> dict[str, Any]:
    items = _intel(ctx).expectations(args.subject)
    return {
        "count": len(items),
        "expectations": [
            {
                "id": e.id,
                "statement": e.statement,
                "kind": e.kind,
                "status": e.status,
                "confidence": e.confidence.value,
                "data_sensitivity": e.data_sensitivity,
                "criticality": e.criticality,
                "subject_ref": e.subject_ref,
                "sources": [
                    {
                        "path": s.path,
                        "start_line": s.span.start_line if s.span else None,
                        "end_line": s.span.end_line if s.span else None,
                    }
                    for s in e.sources
                ],
            }
            for e in items
        ],
    }


def h_history(ctx: ToolContext, args: HistoryArgs) -> dict[str, Any]:
    history: FindingsHistory = ctx.service("history")
    records = history.for_subject(args.subject)
    return {"count": len(records), "records": records[:20]}


_RISK_PATTERNS: list[tuple[str, str, str]] = [
    (r"\beval\(|\bexec\(", "CWE-95", "dynamic code evaluation"),
    (r"subprocess\.|os\.system\(", "CWE-78", "process execution"),
    (r"verify\s*=\s*False", "CWE-295", "certificate verification disabled"),
    (r"f\"\s*(SELECT|INSERT|UPDATE|DELETE)\b|%\s*\(.*\)s\"", "CWE-89", "string-built SQL"),
    (r"\bdebug\s*=\s*True", "CWE-489", "debug mode enabled"),
    (r"allow_origins\s*=\s*\[\s*[\"']\*", "CWE-942", "permissive CORS"),
]


def h_static_analyze(ctx: ToolContext, args: StaticAnalyzeArgs) -> dict[str, Any]:
    """Read-only structural analysis: handler/dependency shape plus pattern signals.

    No third-party analyzer is pinned yet (INFRA-005); this reports the Python
    AST facts the registry can compute itself and is labelled accordingly.
    """
    intel = _intel(ctx)
    rel = safe_rel_path(args.path)
    if not intel.snapshot.exists(rel):
        return {"error": "NOT_FOUND", "detail": f"{rel} is not in the snapshot"}
    text = (intel.snapshot.root / rel).read_text(encoding="utf-8", errors="replace")
    signals: list[dict[str, Any]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        for pattern, cwe, label in _RISK_PATTERNS:
            if re.search(pattern, line):
                signals.append({"line": i, "cwe": cwe, "signal": label, "text": line.strip()[:200]})
    functions: list[dict[str, Any]] = []
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        return {"error": "SYNTAX_ERROR", "detail": str(exc)[:200]}
    for sym in intel.symbols():
        if sym.path != rel or sym.kind == "class":
            continue
        functions.append(
            {
                "symbol": sym.qualified_name,
                "lines": [sym.start_line, sym.end_line],
                "params": list(sym.params),
                "decorators": list(sym.decorators),
                "calls": list(sym.calls),
            }
        )
    suspicious = _suspicious_instructions(text)
    return {
        "analyzer": "python-ast+pattern-rules (no pinned third-party analyzer yet)",
        "path": rel,
        "module_docstring": (ast.get_docstring(tree) or "")[:300],
        "functions": functions[:40],
        "pattern_signals": signals[:20],
        "suspicious_instruction_signals": suspicious[:5],
    }


_INJECTION_RULES = (
    r"(?i)ignore (all |the )?(previous|prior|above) instructions",
    r"(?i)you are (now )?(an? )?(unrestricted|admin|root)",
    r"(?i)skip (the )?(verification|approval|security) (step|check|gate)",
    r"(?i)(do not|don't) (run|execute) (the )?tests",
    r"(?i)mark (this|it) as (verified|approved|safe)",
    r"(?i)system prompt|<\s*/?\s*system\s*>",
)


def _suspicious_instructions(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        for rule in _INJECTION_RULES:
            if re.search(rule, line):
                out.append({"line": i, "text": line.strip()[:200], "rule": rule[:40]})
                break
    return out


def h_list_templates(ctx: ToolContext, args: ListTemplatesArgs) -> dict[str, Any]:
    library: CheckLibrary = ctx.service("checks")
    items = library.list_public()
    if args.category:
        items = [t for t in items if t["category"] == args.category]
    allowed = sorted(ctx.scope.allowed_check_categories) if ctx.scope else []
    return {
        "count": len(items),
        "templates": items,
        "scope_allowed_categories": allowed,
        "note": "Only templates whose category is scope-allowed and runnable can be executed.",
    }


def h_run_template(ctx: ToolContext, args: RunTemplateArgs) -> dict[str, Any]:
    """Scope-checked by the registry before this runs. Executes one reviewed template."""
    runner = ctx.service("check_runner")
    result = runner.run(ctx, args.template_ref, args.target_id, dict(args.parameters))
    ctx.artifacts.setdefault("check_runs", []).append(result)
    return result


def h_write_file(ctx: ToolContext, args: WriteFileArgs) -> dict[str, Any]:
    worktree = ctx.service("worktree")
    return worktree.write_file(args.path, args.content)


def h_diff(ctx: ToolContext, args: DiffArgs) -> dict[str, Any]:
    worktree = ctx.service("worktree")
    return worktree.diff()


def h_tests_run(ctx: ToolContext, args: TestsRunArgs) -> dict[str, Any]:
    runner = ctx.service("test_runner")
    result = runner.run(ctx, args.selection, list(args.node_ids))
    ctx.artifacts.setdefault("test_runs", []).append(result)
    return result


def h_apply_fresh(ctx: ToolContext, args: ApplyFreshArgs) -> dict[str, Any]:
    applier = ctx.service("patch_applier")
    return applier.apply_fresh(ctx, args.patch_id)


# --------------------------------------------------------------------------- catalog

CATALOG: dict[str, ToolDef] = {
    "code.read_span": ToolDef(
        name="code.read_span",
        version="1",
        description="Read an exact line span from a file in the pinned snapshot, with line numbers.",
        args_model=ReadSpanArgs,
        side_effects="none",
        requires_scope=False,
        handler=h_read_span,
    ),
    "code.search": ToolDef(
        name="code.search",
        version="1",
        description="Lexical regular-expression search across the snapshot; returns path, line and text.",
        args_model=SearchArgs,
        side_effects="none",
        requires_scope=False,
        handler=h_search,
    ),
    "graph.neighbors": ToolDef(
        name="graph.neighbors",
        version="1",
        description="Structural neighbours of a symbol: location, decorators, parameters, callees and callers.",
        args_model=NeighborsArgs,
        side_effects="none",
        requires_scope=False,
        handler=h_neighbors,
    ),
    "expectations.for_subject": ToolDef(
        name="expectations.for_subject",
        version="1",
        description="Behavioural expectations (intended behaviour) for a file or symbol, with their sources.",
        args_model=ExpectationsArgs,
        side_effects="none",
        requires_scope=False,
        handler=h_expectations,
    ),
    "findings.history": ToolDef(
        name="findings.history",
        version="1",
        description="Previously recorded hypotheses and findings, including ones already refuted.",
        args_model=HistoryArgs,
        side_effects="none",
        requires_scope=False,
        handler=h_history,
    ),
    "static.analyze": ToolDef(
        name="static.analyze",
        version="1",
        description="Read-only structural analysis of one Python file: handlers, dependencies, pattern signals.",
        args_model=StaticAnalyzeArgs,
        side_effects="none",
        requires_scope=False,
        handler=h_static_analyze,
    ),
    "checks.list_templates": ToolDef(
        name="checks.list_templates",
        version="1",
        description="List reviewed check templates with their categories and required parameters.",
        args_model=ListTemplatesArgs,
        side_effects="none",
        requires_scope=False,
        handler=h_list_templates,
    ),
    "checks.run_template": ToolDef(
        name="checks.run_template",
        version="1",
        description=(
            "Run one reviewed check template against the authorized sandbox target and return its "
            "structured result, including a deterministic matches_expectation field."
        ),
        args_model=RunTemplateArgs,
        side_effects="network_target_only",
        requires_scope=True,
        handler=h_run_template,
        scope_action="run_check",
        category_from="template_ref",
        target_from="target_id",
        timeout_s=240.0,
    ),
    "worktree.write_file": ToolDef(
        name="worktree.write_file",
        version="1",
        description="Write a file inside the isolated patch worktree. Paths outside it are rejected.",
        args_model=WriteFileArgs,
        side_effects="worktree_write",
        requires_scope=False,
        handler=h_write_file,
    ),
    "worktree.diff": ToolDef(
        name="worktree.diff",
        version="1",
        description="Unified diff of the worktree against the pinned snapshot.",
        args_model=DiffArgs,
        side_effects="none",
        requires_scope=False,
        handler=h_diff,
    ),
    "tests.run": ToolDef(
        name="tests.run",
        version="1",
        description="Run the project's test suite (or just the added tests) in a no-network sandbox.",
        args_model=TestsRunArgs,
        side_effects="sandbox_exec",
        requires_scope=False,
        handler=h_tests_run,
        timeout_s=480.0,
    ),
    "patch.apply_fresh": ToolDef(
        name="patch.apply_fresh",
        version="1",
        description="Apply the candidate diff to a fresh checkout of the snapshot in a new sandbox workspace.",
        args_model=ApplyFreshArgs,
        side_effects="sandbox_exec",
        requires_scope=False,
        handler=h_apply_fresh,
    ),
}


def default_registry() -> ToolRegistry:
    return ToolRegistry(CATALOG)
