"""Adapter from Sarosh's `code_intelligence.IntelligenceService` to the `CodeIntel` port.

This is the real integration: when it is used, the agents read spans, symbols,
the call graph and expectations out of the indexed snapshot rather than out of
this package's local Python-`ast` fallback.

Two facts shape the adapter:

* the service is keyed by a `SnapshotRef` and returns canonical `shared`
  models, so `snapshot()` here exposes the indexed commit, not a directory copy;
* the sandbox still needs a real tree on disk to copy into a container, and the
  index does not hand out one, so a `workspace` path is supplied alongside the
  ref. The adapter checks that the workspace matches the indexed snapshot's
  files before it is used for anything executable.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from ..contracts import (
    BehavioralExpectation,
    Confidence,
    EntryPoint,
    ErrorCode,
    EvidenceRef,
    PlatformError,
    SourceSpan,
)
from ..sandbox.workspace import SnapshotHandle, safe_rel_path
from .port import MAX_SPAN_LINES, Span, SymbolInfo

# docs/12 expectation statuses; the canonical model may use a different vocabulary.
_STATUS_MAP = {
    "confirmed": "confirmed",
    "inferred": "inferred",
    "ambiguous": "ambiguous",
    "conflicting": "conflicting",
    "proposed": "inferred",
}

_CRITICALITY = {"financial": "high", "personal": "high", "internal": "medium", "none": "low"}


def _value(obj: Any, default: str = "") -> str:
    return str(getattr(obj, "value", obj) if obj is not None else default)


@dataclass
class CodeIntelligenceAdapter:
    """`CodeIntel` over an indexed snapshot.

    `service` is a `code_intelligence.api.IntelligenceService`; `ref` is the
    `SnapshotRef` it returned from `index_repository`. `workspace` is the
    checked-out tree for that exact commit, used only by the sandbox.
    """

    service: Any
    ref: Any
    workspace: Path
    index_version: str = ""
    path_prefix: str | None = None
    """Prefix the index uses for the indexed subtree (e.g. `target/`).

    The index stores repository-relative paths, which include the binding's
    include prefix; the sandbox workspace is that subtree. Paths handed to
    agents are workspace-relative (citation validation and the patch worktree
    depend on that), so the adapter strips the prefix on the way out and adds it
    back on the way in. Auto-detected when not given.
    """

    # ------------------------------------------------------------------ snapshot

    @cached_property
    def _handle(self) -> SnapshotHandle:
        return SnapshotHandle(
            snapshot_id=str(getattr(self.ref, "snapshot_id", "")),
            repo_id=str(getattr(self.ref, "repo_id", "")),
            commit_sha=str(getattr(self.ref, "commit_sha", "")),
            root=self.workspace,
            pinned_by="code_intelligence",
        )

    @property
    def snapshot(self) -> SnapshotHandle:
        return self._handle

    def provenance(self) -> dict[str, str]:
        return {
            "adapter": "security_agents.intel.CodeIntelligenceAdapter",
            "status": "live index (code_intelligence.api)",
            "service": type(self.service).__name__,
            "index_version": self.index_version or str(getattr(self.ref, "index_version", "")),
            "snapshot_id": self._handle.snapshot_id,
            "commit_sha": self._handle.commit_sha,
            "pinned_by": self._handle.pinned_by,
            "expectations_origin": "derived by code_intelligence",
        }

    def verify_workspace(self) -> None:
        """Refuse to execute against a tree that is not the indexed snapshot."""
        indexed = {s.path for s in self.symbols()}
        if not indexed:
            return
        missing = [path for path in sorted(indexed) if not (self.workspace / path).is_file()]
        if missing:
            raise PlatformError(
                ErrorCode.SNAPSHOT_NOT_READY,
                f"workspace does not match the indexed snapshot (missing {missing[:3]})",
            )

    @cached_property
    def _prefix(self) -> str:
        if self.path_prefix is not None:
            return self.path_prefix.strip("/") + "/" if self.path_prefix.strip("/") else ""
        paths = [str(getattr(symbol, "path", "")) for symbol in self._symbols]
        candidate = f"{self.workspace.name}/"
        if paths and all(path.startswith(candidate) for path in paths):
            return candidate
        return ""

    def _to_index(self, path: str) -> str:
        """Workspace-relative path -> the path the index knows."""
        prefix = self._prefix
        return path if not prefix or path.startswith(prefix) else f"{prefix}{path}"

    def _to_workspace(self, path: str) -> str:
        """Index path -> workspace-relative path."""
        prefix = self._prefix
        return path[len(prefix) :] if prefix and path.startswith(prefix) else path

    # ------------------------------------------------------------------ reading

    def read_span(self, path: str, start_line: int, end_line: int) -> Span:
        rel = safe_rel_path(path)
        start = max(1, int(start_line))
        end = max(start, int(end_line))
        if end - start + 1 > MAX_SPAN_LINES:
            end = start + MAX_SPAN_LINES - 1
        try:
            content = self.service.read_span(self.ref, self._to_index(rel), start, end)
        except Exception as exc:
            raise PlatformError(ErrorCode.SCHEMA_INVALID, f"read_span failed: {exc}"[:300]) from exc
        numbered = "\n".join(
            f"{number:>5}  {line}"
            for number, line in enumerate(content.splitlines(), start=start)
        )
        return Span(path=rel, start_line=start, end_line=end, content=numbered)

    def search(self, pattern: str, *, max_results: int = 20) -> list[dict[str, Any]]:
        """Literal search. NOTE: the service matches case-insensitive substrings,
        not regular expressions, so a regex from an agent is used as text."""
        try:
            chunks = self.service.search(self.ref, pattern, limit=max(1, min(max_results, 50)))
        except Exception as exc:
            raise ValueError(f"search failed: {exc}"[:200]) from exc
        hits: list[dict[str, Any]] = []
        for chunk in chunks:
            provenance = getattr(chunk, "provenance", None)
            span = getattr(provenance, "span", None)
            hits.append(
                {
                    "path": self._to_workspace(str(getattr(provenance, "path", ""))),
                    "line": int(getattr(span, "start_line", 0) or 0),
                    "text": _strip_delimiters(str(getattr(chunk, "content", "")))[:300],
                }
            )
        return hits

    # ------------------------------------------------------------------ structure

    @cached_property
    def _index(self) -> Any:
        """The stored index.

        `calls` (directed `CallEdge`s with a `resolution`) is what Scout's
        sibling comparison needs and the public service API does not expose it
        yet, so the adapter reads it from the store. A public accessor was
        requested from the owner; until then this is the one place that reaches
        past the service API.
        """
        return self.service.store.get(self.ref)

    @cached_property
    def _symbols(self) -> list[Any]:
        out: list[Any] = []
        offset = 0
        while True:
            page = self.service.symbols(self.ref, offset=offset, limit=100)
            out.extend(page)
            if len(page) < 100:
                return out
            offset += len(page)

    def symbols(self) -> list[SymbolInfo]:
        return [
            SymbolInfo(
                qualified_name=str(getattr(symbol, "qualified_name", "")),
                kind=_value(getattr(symbol, "kind", "function")),
                path=self._to_workspace(str(getattr(symbol, "path", ""))),
                start_line=int(getattr(symbol, "start_line", 1) or 1),
                end_line=int(getattr(symbol, "end_line", 1) or 1),
                decorators=tuple(getattr(symbol, "decorators", ()) or ()),
                calls=tuple(self._callees_of(str(getattr(symbol, "id", "")))),
                params=tuple(_params_from_signature(getattr(symbol, "signature", None))),
            )
            for symbol in self._symbols
        ]

    def find_symbol(self, name: str) -> SymbolInfo | None:
        candidates = self.symbols()
        for symbol in candidates:
            if symbol.qualified_name == name:
                return symbol
        return next(
            (s for s in candidates if s.qualified_name.rsplit(".", 1)[-1] == name), None
        )

    def _symbol_id(self, name: str) -> str | None:
        for symbol in self._symbols:
            qualified = str(getattr(symbol, "qualified_name", ""))
            if name in (qualified, str(getattr(symbol, "id", ""))):
                return str(getattr(symbol, "id", ""))
        for symbol in self._symbols:
            if str(getattr(symbol, "qualified_name", "")).rsplit(".", 1)[-1] == name:
                return str(getattr(symbol, "id", ""))
        return None

    def _name_of(self, symbol_id: str) -> str:
        for symbol in self._symbols:
            if str(getattr(symbol, "id", "")) == symbol_id:
                return str(getattr(symbol, "qualified_name", symbol_id))
        return symbol_id

    def _callees_of(self, symbol_id: str) -> list[str]:
        """Directed callees, each labelled with the index's resolution quality."""
        out: list[str] = []
        for edge in getattr(self._index, "calls", ()) or ():
            if str(getattr(edge, "caller_id", "")) != symbol_id:
                continue
            resolution = _value(getattr(edge, "resolution", "unresolved"), "unresolved")
            callee_id = getattr(edge, "callee_id", None)
            name = self._name_of(str(callee_id)) if callee_id else str(getattr(edge, "callee_name", ""))
            out.append(name if resolution == "exact" else f"{name} ({resolution})")
        return sorted(set(out))

    def _callers_of(self, symbol_id: str) -> list[str]:
        out = {
            self._name_of(str(getattr(edge, "caller_id", "")))
            for edge in getattr(self._index, "calls", ()) or ()
            if str(getattr(edge, "callee_id", "")) == symbol_id
        }
        return sorted(out)

    def neighbors(self, qualified_name: str) -> dict[str, list[str]]:
        symbol_id = self._symbol_id(qualified_name)
        if symbol_id is None:
            return {"error": [f"unknown symbol {qualified_name}"], "callees": [], "callers": []}
        target = next((s for s in self._symbols if str(getattr(s, "id", "")) == symbol_id), None)
        return {
            "symbol": [str(getattr(target, "qualified_name", qualified_name))],
            "location": [
                f"{self._to_workspace(str(getattr(target, 'path', '')))}:"
                f"{getattr(target, 'start_line', '?')}-{getattr(target, 'end_line', '?')}"
            ],
            "decorators": list(getattr(target, "decorators", ()) or ()),
            "params": list(_params_from_signature(getattr(target, "signature", None))),
            "callees": self._callees_of(symbol_id),
            "callers": self._callers_of(symbol_id),
        }

    def entry_points(self) -> list[EntryPoint]:
        out: list[EntryPoint] = []
        offset = 0
        while True:
            page = self.service.entry_points(self.ref, offset=offset, limit=100)
            for entry in page:
                handler_id = str(getattr(entry, "handler_symbol_id", ""))
                handler = next(
                    (
                        str(getattr(s, "qualified_name", ""))
                        for s in self._symbols
                        if str(getattr(s, "id", "")) == handler_id
                    ),
                    handler_id,
                )
                symbol = next(
                    (s for s in self._symbols if str(getattr(s, "id", "")) == handler_id), None
                )
                out.append(
                    EntryPoint(
                        id=str(getattr(entry, "id", "")),
                        snapshot_id=self._handle.snapshot_id,
                        kind=_value(getattr(entry, "kind", "http_route")) or "http_route",  # type: ignore[arg-type]
                        handler_symbol=handler,
                        path=self._to_workspace(str(getattr(symbol, "path", "") or "unknown")),
                        span=SourceSpan(
                            start_line=int(getattr(symbol, "start_line", 1) or 1),
                            end_line=int(getattr(symbol, "end_line", 1) or 1),
                        ),
                        method=getattr(entry, "method", None),
                        path_template=getattr(entry, "path_template", None),
                        auth_dependencies=list(getattr(entry, "auth_dependencies", ()) or ()),
                    )
                )
            if len(page) < 100:
                return out
            offset += len(page)

    # ------------------------------------------------------------------ expectations

    def expectations(self, subject_ref: str | None = None) -> list[BehavioralExpectation]:
        try:
            records = self.service.expectations(self.ref, subject_ref, offset=0, limit=100)
        except Exception:
            records = []
        if not records and subject_ref is not None:
            records = self.service.expectations(self.ref, None, offset=0, limit=100)
        return [self._expectation(record) for record in records]

    def _expectation(self, record: Any) -> BehavioralExpectation:
        sensitivity = _value(getattr(record, "data_sensitivity", None), "none") or "none"
        sources: list[EvidenceRef] = []
        for source in getattr(record, "sources", ()) or ():
            span = getattr(source, "span", None)
            sources.append(
                EvidenceRef(
                    path=(
                        self._to_workspace(str(source.path))
                        if getattr(source, "path", None)
                        else None
                    ),
                    sha=getattr(source, "commit_sha", None) or self._handle.commit_sha,
                    span=(
                        SourceSpan(
                            start_line=int(getattr(span, "start_line", 1) or 1),
                            end_line=int(getattr(span, "end_line", 1) or 1),
                        )
                        if span is not None
                        else None
                    ),
                    symbol=getattr(source, "symbol", None),
                    provenance="expectation",
                )
            )
        confidence_raw = getattr(record, "confidence", 0.6)
        confidence = (
            Confidence(_value(confidence_raw))
            if isinstance(confidence_raw, str)
            else _confidence_from_score(float(confidence_raw))
        )
        return BehavioralExpectation(
            id=str(getattr(record, "id", "")),
            snapshot_id=self._handle.snapshot_id,
            subject_ref=str(getattr(record, "subject_ref", "")),
            statement=str(getattr(record, "statement", ""))[:2000],
            kind=_value(getattr(record, "kind", "functional")) or "functional",
            sources=sources,
            confidence=confidence,
            origin=_origin(_value(getattr(record, "origin", "inferred"))),
            status=_STATUS_MAP.get(_value(getattr(record, "status", "inferred")), "inferred"),  # type: ignore[arg-type]
            data_sensitivity=sensitivity if sensitivity in _CRITICALITY else None,  # type: ignore[arg-type]
            criticality=_CRITICALITY.get(sensitivity, "medium"),  # type: ignore[arg-type]
        )


def _origin(raw: str) -> str:
    return raw if raw in ("test", "doc", "spec", "inferred", "fixture") else "inferred"


def _confidence_from_score(score: float) -> Confidence:
    if score >= 0.75:
        return Confidence.HIGH
    if score >= 0.45:
        return Confidence.MEDIUM
    return Confidence.LOW


def _params_from_signature(signature: Any) -> list[str]:
    """Parameter names out of a `def f(a, b=1)`-style signature string."""
    if not signature:
        return []
    text = str(signature)
    if "(" not in text or ")" not in text:
        return []
    inner = text[text.index("(") + 1 : text.rindex(")")]
    names: list[str] = []
    depth = 0
    current = ""
    for char in inner:
        if char in "[({":
            depth += 1
        elif char in "])}":
            depth -= 1
        if char == "," and depth == 0:
            names.append(current)
            current = ""
        else:
            current += char
    names.append(current)
    out = []
    for raw in names:
        name = raw.split(":")[0].split("=")[0].strip().lstrip("*")
        if name and name not in ("self", "cls"):
            out.append(name)
    return out


def _strip_delimiters(text: str) -> str:
    """Drop the service's untrusted-data wrapper so a search hit reads as a line."""
    lines = [
        line
        for line in text.splitlines()
        if not line.startswith(("<untrusted", "</untrusted", "<data", "</data"))
    ]
    return " ".join(line.strip() for line in lines if line.strip())
