"""Code-intelligence port + local adapter.

The runtime depends on the narrow CodeIntel protocol. Production host mode uses
CodeIntelligenceAdapter over code_intelligence.api and a Git-pinned workspace;
LocalIntel remains an explicit development/test fixture adapter. Provenance
identifies the producer and mode so directory fixtures cannot imply live index proof.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Protocol

from ..contracts import (
    BehavioralExpectation,
    Confidence,
    EntryPoint,
    EvidenceRef,
    SourceSpan,
    new_id,
)
from ..sandbox.workspace import SnapshotHandle, resolve_under, safe_rel_path

MAX_SPAN_LINES = 400


@dataclass(frozen=True)
class Span:
    path: str
    start_line: int
    end_line: int
    content: str

    def evidence(self, sha: str, symbol: str | None = None) -> EvidenceRef:
        return EvidenceRef(
            path=self.path,
            sha=sha,
            span=SourceSpan(start_line=self.start_line, end_line=self.end_line),
            symbol=symbol,
            provenance="code",
        )


@dataclass(frozen=True)
class SymbolInfo:
    qualified_name: str
    kind: str
    path: str
    start_line: int
    end_line: int
    decorators: tuple[str, ...]
    calls: tuple[str, ...]
    params: tuple[str, ...]


class CodeIntel(Protocol):
    @property
    def snapshot(self) -> SnapshotHandle: ...

    def provenance(self) -> dict[str, str]: ...

    def read_span(self, path: str, start_line: int, end_line: int) -> Span: ...

    def search(self, pattern: str, *, max_results: int = 20) -> list[dict[str, Any]]: ...

    def symbols(self) -> list[SymbolInfo]: ...

    def neighbors(self, qualified_name: str) -> dict[str, list[str]]: ...

    def entry_points(self) -> list[EntryPoint]: ...

    def expectations(self, subject_ref: str | None = None) -> list[BehavioralExpectation]: ...


_HTTP_DECORATORS = ("get", "post", "put", "patch", "delete")


class LocalIntel:
    """Python-only structural index over a pinned snapshot directory."""

    def __init__(
        self, snapshot: SnapshotHandle, expectations: list[BehavioralExpectation] | None = None
    ) -> None:
        self._snapshot = snapshot
        self._injected = expectations

    @property
    def snapshot(self) -> SnapshotHandle:
        return self._snapshot

    def provenance(self) -> dict[str, str]:
        return {
            "adapter": "security_agents.intel.LocalIntel",
            "status": "LOCAL ADAPTER pending code_intelligence.api (INTEL-007)",
            "expectations_origin": (
                "injected (labels fixture)" if self._injected is not None else "expectations.json or none"
            ),
            "parser": "python-ast",
            "languages": "python",
            "call_resolution": "name-based, confidence=likely",
            "snapshot_id": self._snapshot.snapshot_id,
            "commit_sha": self._snapshot.commit_sha,
            "pinned_by": self._snapshot.pinned_by,
        }

    # ------------------------------------------------------------------ reading

    def read_span(self, path: str, start_line: int, end_line: int) -> Span:
        rel = safe_rel_path(path)
        target = resolve_under(self._snapshot.root, rel)
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(start_line))
        end = min(len(lines), int(end_line))
        if end < start:
            end = start
        if end - start + 1 > MAX_SPAN_LINES:
            end = start + MAX_SPAN_LINES - 1
        body = "\n".join(f"{n:>5}  {lines[n - 1]}" for n in range(start, min(end, len(lines)) + 1))
        return Span(path=rel, start_line=start, end_line=min(end, len(lines)), content=body)

    def search(self, pattern: str, *, max_results: int = 20) -> list[dict[str, Any]]:
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"invalid regex: {exc}") from exc
        hits: list[dict[str, Any]] = []
        for rel in self._snapshot.files():
            if not rel.endswith((".py", ".md", ".json", ".yaml", ".yml", ".toml", ".cfg", ".txt")):
                continue
            try:
                text = (self._snapshot.root / rel).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    hits.append({"path": rel, "line": i, "text": line.strip()[:300]})
                    if len(hits) >= max_results:
                        return hits
        return hits

    # ------------------------------------------------------------------ structure

    @cached_property
    def _index(self) -> tuple[list[SymbolInfo], list[EntryPoint]]:
        symbols: list[SymbolInfo] = []
        entries: list[EntryPoint] = []
        for rel in self._snapshot.files():
            if not rel.endswith(".py"):
                continue
            source = (self._snapshot.root / rel).read_text(encoding="utf-8", errors="replace")
            try:
                tree = ast.parse(source, filename=rel)
            except SyntaxError:
                continue
            module = rel[:-3].replace("/", ".")
            for node, stack in _walk_defs(tree):
                qname = ".".join([module, *stack, node.name])
                decorators = tuple(_decorator_text(d) for d in node.decorator_list)
                kind = "class" if isinstance(node, ast.ClassDef) else ("method" if stack else "function")
                calls = tuple(sorted(set(_called_names(node))))
                params = tuple(a.arg for a in node.args.args) if not isinstance(node, ast.ClassDef) else ()
                end = int(getattr(node, "end_lineno", node.lineno) or node.lineno)
                symbols.append(
                    SymbolInfo(
                        qualified_name=qname,
                        kind=kind,
                        path=rel,
                        start_line=node.lineno,
                        end_line=end,
                        decorators=decorators,
                        calls=calls,
                        params=params,
                    )
                )
                route = _route_from_decorators(decorators)
                if route is not None and not isinstance(node, ast.ClassDef):
                    method, path_template = route
                    entries.append(
                        EntryPoint(
                            id=f"ent_{method.lower()}_{re.sub(r'[^a-z0-9]+', '_', path_template.lower()).strip('_')}",
                            snapshot_id=self._snapshot.snapshot_id,
                            kind="http_route",
                            handler_symbol=qname,
                            path=rel,
                            span=SourceSpan(start_line=node.lineno, end_line=end),
                            method=method,
                            path_template=path_template,
                            auth_dependencies=sorted(_auth_dependencies(node)),
                        )
                    )
        return symbols, entries

    def symbols(self) -> list[SymbolInfo]:
        return list(self._index[0])

    def entry_points(self) -> list[EntryPoint]:
        return list(self._index[1])

    def find_symbol(self, name: str) -> SymbolInfo | None:
        syms = self._index[0]
        for s in syms:
            if s.qualified_name == name:
                return s
        return next(
            (s for s in syms if s.qualified_name.endswith("." + name) or s.qualified_name == name), None
        )

    def neighbors(self, qualified_name: str) -> dict[str, list[str]]:
        syms = self._index[0]
        target = self.find_symbol(qualified_name)
        if target is None:
            return {"error": [f"unknown symbol {qualified_name}"], "callees": [], "callers": []}
        short = target.qualified_name.rsplit(".", 1)[-1]
        callees: list[str] = []
        for name in target.calls:
            matches = [
                s.qualified_name
                for s in syms
                if s.qualified_name.rsplit(".", 1)[-1] == name and s.qualified_name != target.qualified_name
            ]
            callees.append(
                matches[0]
                if len(matches) == 1
                else (f"{name} (ambiguous: {len(matches)} candidates)" if matches else f"{name} (unresolved)")
            )
        callers = [
            s.qualified_name for s in syms if short in s.calls and s.qualified_name != target.qualified_name
        ]
        return {
            "symbol": [target.qualified_name],
            "location": [f"{target.path}:{target.start_line}-{target.end_line}"],
            "decorators": list(target.decorators),
            "params": list(target.params),
            "callees": callees,
            "callers": callers,
        }

    # ------------------------------------------------------------------ expectations

    @cached_property
    def _expectations(self) -> list[BehavioralExpectation]:
        if self._injected is not None:
            return list(self._injected)
        path = self._snapshot.root / "expectations.json"
        if not path.is_file():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        out: list[BehavioralExpectation] = []
        for item in raw.get("expectations", []):
            sources = [
                EvidenceRef(
                    path=s["path"],
                    sha=self._snapshot.commit_sha,
                    span=SourceSpan(start_line=s["start_line"], end_line=s["end_line"]),
                    provenance="expectation",
                )
                for s in item.get("sources", [])
            ]
            out.append(
                BehavioralExpectation(
                    id=item["id"],
                    snapshot_id=self._snapshot.snapshot_id,
                    subject_ref=item["subject_ref"],
                    statement=item["statement"],
                    kind=item["kind"],
                    sources=sources,
                    confidence=Confidence(item.get("confidence", "medium")),
                    origin="fixture",
                    status=item.get("status", "confirmed"),
                    data_sensitivity=item.get("data_sensitivity"),
                    criticality=item.get("criticality", "medium"),
                )
            )
        return out

    def expectations(self, subject_ref: str | None = None) -> list[BehavioralExpectation]:
        items = self._expectations
        if subject_ref is None:
            return list(items)
        needle = subject_ref.strip()
        return [
            e for e in items if needle in e.subject_ref or e.subject_ref in needle or needle in e.statement
        ] or list(items)


# --------------------------------------------------------------------------- ast helpers

Def = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


def _walk_defs(tree: ast.AST, stack: tuple[str, ...] = ()) -> list[tuple[Def, tuple[str, ...]]]:
    out: list[tuple[Def, tuple[str, ...]]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            out.append((node, stack))
            out.extend(_walk_defs(node, (*stack, node.name)))
        else:
            out.extend(_walk_defs(node, stack))
    return out


def _decorator_text(node: ast.expr) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "<decorator>"


def _called_names(node: ast.AST) -> list[str]:
    names: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                names.append(func.id)
            elif isinstance(func, ast.Attribute):
                names.append(func.attr)
    return names


def _route_from_decorators(decorators: tuple[str, ...]) -> tuple[str, str] | None:
    for dec in decorators:
        m = re.match(r"^[\w.]*\.(" + "|".join(_HTTP_DECORATORS) + r")\(\s*['\"]([^'\"]+)['\"]", dec)
        if m:
            return m.group(1).upper(), m.group(2)
    return None


def _auth_dependencies(node: Def) -> set[str]:
    """Dependency callables wired into the handler signature (FastAPI `Depends`)."""
    deps: set[str] = set()
    if isinstance(node, ast.ClassDef):
        return deps
    for default in list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]:
        if isinstance(default, ast.Call) and isinstance(default.func, ast.Name | ast.Attribute):
            fname = default.func.id if isinstance(default.func, ast.Name) else default.func.attr
            if fname == "Depends" and default.args:
                arg = default.args[0]
                if isinstance(arg, ast.Name):
                    deps.add(arg.id)
                elif isinstance(arg, ast.Attribute):
                    deps.add(arg.attr)
    return deps


@dataclass
class FindingsHistory:
    """Prior hypotheses/findings for the project (durable store lives in backend)."""

    records: list[dict[str, Any]] = field(default_factory=list)

    def for_subject(self, subject: str | None = None) -> list[dict[str, Any]]:
        if subject is None:
            return list(self.records)
        return [r for r in self.records if subject in json.dumps(r, default=str)]

    def refuted_keys(self) -> list[str]:
        return [r["key"] for r in self.records if r.get("outcome") == "refuted" and "key" in r]


def hypothesis_key(weakness_class: str, path: str, symbol: str | None) -> str:
    return f"{weakness_class}:{path}:{symbol or '-'}"


def new_snapshot_id() -> str:
    return new_id("snp")
