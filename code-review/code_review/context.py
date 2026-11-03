"""Deterministic change context for the reviewer's first turn.

A cross-file contract break (a renamed field, a reordered signature) is invisible in the
diff alone: the broken caller is in a file the change did not touch. Before the model
starts, this module lists where the changed symbols are referenced across the pinned head
tree, which identifiers the change removed while other code still uses them, and which
tests and docs mention the changed code. Plain text search, language-agnostic, bounded;
the model must still read the lines before citing them.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from code_review.models import CitationIn, SourceKind
from code_review.workspace import Workspace, WorkspaceError, is_denied_read, is_test_path

_IDENT = r"[A-Za-z_$][\w$]*"
_DEF = re.compile(
    rf"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:def|class|function\*?)\s+({_IDENT})"
    rf"|^\s*(?:export\s+)?(?:const|let|var)\s+({_IDENT})\s*=\s*(?:async\s*)?"
    rf"(?:function\b|\([^)]*\)\s*=>|{_IDENT}\s*=>)"
)
_HUNK = re.compile(r"^@@ [^@]* @@\s?(.*)$")
_HUNK_RANGE = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@")
_NEW_START = re.compile(r"\+(\d+)")
_WORD = re.compile(_IDENT)
_COMMENT = re.compile(r"^\s*(#|//|/?\*)")
_SEARCHED = (".py", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".html")
_DOCS = (".md", ".rst", ".txt")
# Words too common to say anything about a contract.
_STOP = frozenset(
    (
        "self this none null true false return const function async await import export from "
        "default class def let var await raise throw string number object value result data "
        "error index items item key keys args kwargs"
    ).split()
)
MAX_FILE_BYTES = 512_000
MAX_SYMBOLS, MAX_REMOVED, MAX_REFS, MAX_CHARS = 10, 12, 8, 8_000


def _enclosing(head: Workspace, rel: str, line_no: int) -> str | None:
    """Name of the nearest definition at or above ``line_no`` in the head file."""
    try:
        lines = head.read(rel).splitlines()[:line_no]
    except (WorkspaceError, OSError):
        return None
    for text in reversed(lines):
        if d := _DEF.match(text):
            return d.group(1) or d.group(2)
    return None


def _changed_symbols(head: Workspace, diff: str) -> tuple[list[str], list[str]]:
    """(symbols defined in or enclosing the changed hunks, identifiers only on removed lines)."""
    symbols: dict[str, None] = {}
    removed: dict[str, None] = {}
    added: set[str] = set()
    path, new_line, located, header = "", 0, True, None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:].removeprefix("b/")
            continue
        if line.startswith("---"):
            continue
        if m := _HUNK.match(line):
            # git's hunk label is often the previous function, so it is only a fallback
            d = _DEF.match(m.group(1))
            header = (d.group(1) or d.group(2)) if d else None
            start = _NEW_START.search(line)
            new_line, located = int(start.group(1)) if start else 0, False
            continue
        if line[:1] in "+-":
            if not located:
                name = _enclosing(head, path, max(new_line, 1)) if path else None
                if name or header:
                    symbols[name or header] = None  # type: ignore[index]
                located = True
            text = line[1:]
            words = _WORD.findall(text)
            if line[0] == "-":
                removed.update(dict.fromkeys(words))
            else:
                added.update(words)
        else:
            new_line += 1
            continue
        if line[:1] == "+":
            new_line += 1
        if d := _DEF.match(text):
            symbols[d.group(1) or d.group(2)] = None
    gone = [w for w in removed if w not in added and len(w) >= 4 and w.lower() not in _STOP]
    names = [s for s in symbols if len(s) >= 3 and s.lower() not in _STOP]
    return names[:MAX_SYMBOLS], gone[:MAX_REMOVED]


def change_context(head: Workspace, diff: str, changed: list[str]) -> str:
    """The ``<change_context>`` block for the reviewer prompt, or "" when there is no diff."""
    if not diff:
        return ""
    symbols, removed = _changed_symbols(head, diff)
    names = [*symbols, *(r for r in removed if r not in symbols)]
    stems = {PurePosixPath(p).stem for p in changed if len(PurePosixPath(p).stem) >= 4}
    rx = (
        re.compile(r"(?<![\w$])(" + "|".join(map(re.escape, names)) + r")(?![\w$])")
        if names
        else None
    )
    refs: dict[str, list[str]] = {n: [] for n in names}
    tests: dict[str, None] = {}
    docs: dict[str, None] = {}
    for rel in head.files():
        if is_denied_read(rel) or not rel.endswith(_SEARCHED + _DOCS):
            continue
        try:
            if head.path(rel).stat().st_size > MAX_FILE_BYTES:
                continue
            text = head.read(rel)
        except (WorkspaceError, OSError):
            continue
        is_doc = rel.endswith(_DOCS)
        mentions = any(s in text for s in stems)
        if rx is not None:
            for n, line in enumerate(text.splitlines(), 1):
                for name in dict.fromkeys(rx.findall(line)):
                    if is_doc:
                        mentions = True
                    elif (
                        len(refs[name]) < MAX_REFS
                        and not _DEF.match(line)
                        and not _COMMENT.match(line)
                    ):
                        refs[name].append(f"  {rel}:{n}: {line.strip()[:160]}")
        if mentions and rel not in changed:
            if is_doc:
                docs[rel] = None
            elif is_test_path(rel):
                tests[rel] = None
    out = ['<change_context source="text search at head; read the lines before citing them">']
    for name in symbols:
        if refs[name]:
            out.append(f"references to changed symbol `{name}`:")
            out += refs[name]
    for name in removed:
        if name not in symbols and refs[name]:
            out.append(f"`{name}` was removed from changed lines; other uses to re-check:")
            out += refs[name]
    if tests:
        out.append("tests mentioning the changed code: " + ", ".join(list(tests)[:12]))
    if docs:
        out.append("docs mentioning the changed code: " + ", ".join(list(docs)[:12]))
    if len(out) == 1:
        return ""
    text = "\n".join(out)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n... (truncated)"
    return text + "\n</change_context>"


def hunk_citations(diff: str, cited: list[CitationIn]) -> list[CitationIn]:
    """Quote-free code citations of the head-side changed lines, one per hunk, of each file
    the model cited. Used only when none of its quotes verify at head."""
    paths = {c.path for c in cited if c.path}
    out: list[CitationIn] = []
    path = ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:].removeprefix("b/")
        elif path in paths and (m := _HUNK_RANGE.match(line)):
            start, count = int(m.group(1)), int(m.group(2) or 1)
            out.append(
                CitationIn(
                    source_kind=SourceKind.code,
                    path=path,
                    start_line=max(start, 1),
                    end_line=max(start + count - 1, start, 1),
                )
            )
    return out
