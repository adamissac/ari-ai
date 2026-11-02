"""Syntactic HTTP route detection for JavaScript/TypeScript (ADR-0023).

Recognises Next.js App Router and Pages API files, Vercel functions, Express calls and
Firebase Cloud Functions `onRequest` exports. Anything else (dynamic route tables, custom
servers) is not detected; nothing here executes repository code.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

import tree_sitter_javascript
import tree_sitter_typescript
from shared.intelligence import EntryPoint, EntryPointKind, SnapshotRef, Symbol, SymbolKind
from tree_sitter import Language, Node, Parser

from code_intelligence.models import IndexIssue, SourceFile, stable_id

VERBS = ("GET", "POST", "PUT", "PATCH", "DELETE")
_EXPRESS_VERBS = {v.lower() for v in VERBS} | {"all"}
_APP_ROUTE = re.compile(r"(?:^|/)app/((?:.+/)?)route\.(?:[cm]?js|ts)$")
_PAGES_API = re.compile(r"(?:^|/)pages/(api(?:/.+)?)\.(?:[cm]?js|jsx|ts|tsx)$")
_VERCEL_API = re.compile(r"^(api(?:/.+)?)\.(?:[cm]?js|ts)$")
_AUTH_SIGNALS = (
    "verifyIdToken",
    "verifySessionCookie",
    "getServerSession",
    "getToken",
    "authorization",
)
_CANDIDATE = re.compile(r"""['"]express['"]|\bonRequest\b""")
_METHOD_LITERAL = re.compile(r"""['"](GET|POST|PUT|PATCH|DELETE)['"]""")

_LANGUAGES = {
    ".ts": Language(tree_sitter_typescript.language_typescript()),
    ".tsx": Language(tree_sitter_typescript.language_tsx()),
}
_JS = Language(tree_sitter_javascript.language())


def _segments_to_template(segments: str) -> str:
    """`users/[id]/(group)/[...slug]` -> `/users/{id}/{slug}`."""
    out = []
    for part in segments.strip("/").split("/"):
        if not part or (part.startswith("(") and part.endswith(")")) or part.startswith("@"):
            continue
        m = re.fullmatch(r"\[\[?(?:\.\.\.)?([A-Za-z_][A-Za-z0-9_]*)\]?\]", part)
        out.append("{" + m.group(1) + "}" if m else part)
    return "/" + "/".join(out)


def _text(node: Node | None) -> str:
    return node.text.decode("utf-8", "replace") if node is not None and node.text else ""


def _walk(node: Node):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


class JsRouteExtractor:
    def __init__(self, ref: SnapshotRef, files: list[SourceFile]) -> None:
        self.ref = ref
        self.files = files
        self.symbols: list[Symbol] = []
        self.entries: list[EntryPoint] = []
        self.issues: list[IndexIssue] = []

    def extract(self) -> None:
        for file in self.files:
            if file.language not in ("javascript", "typescript") or file.is_test:
                continue
            by_path = (
                _APP_ROUTE.search(file.path)
                or _PAGES_API.search(file.path)
                or _VERCEL_API.match(file.path)
            )
            if not by_path and not _CANDIDATE.search(file.content):
                continue  # only candidate files are parsed: data modules stay text
            suffix = PurePosixPath(file.path).suffix
            tree = Parser(_LANGUAGES.get(suffix, _JS)).parse(file.content.encode())
            if tree.root_node.has_error:
                self.issues.append(
                    IndexIssue(path=file.path, reason="Tree-sitter parse error (JS/TS)")
                )
                continue
            root = tree.root_node
            if m := _APP_ROUTE.search(file.path):
                template = _segments_to_template(m.group(1))
                for name, node in self._named_exports(root).items():
                    if name in VERBS:
                        self._emit(file, node, name, name, template)
            elif m := (_PAGES_API.search(file.path) or _VERCEL_API.match(file.path)):
                if PurePosixPath(file.path).name.startswith("_"):
                    continue  # Vercel and Next.js both ignore underscore files
                segments = re.sub(r"(?:^|/)index$", "", m.group(1))
                default = self._default_export(root)
                if default is not None:
                    methods = sorted(set(_METHOD_LITERAL.findall(_text(default)))) or ["ANY"]
                    for method in methods:
                        self._emit(
                            file, default, "default", method, _segments_to_template(segments)
                        )
            self._express(file, root)
            self._cloud_functions(file, root)

    def _emit(self, file: SourceFile, node: Node, name: str, method: str, template: str) -> None:
        start, end = node.start_point[0] + 1, node.end_point[0] + 1
        qualified = re.sub(r"\.[^./]+$", "", file.path).replace("/", ".") + "." + name
        symbol = Symbol(
            id=stable_id("sym", self.ref.snapshot_id, file.path, qualified, str(start)),
            snapshot_id=self.ref.snapshot_id,
            kind=SymbolKind.function,
            qualified_name=qualified[:500],
            path=file.path,
            start_line=start,
            end_line=end,
            signature=_text(node).split("{", 1)[0].strip()[:500] or None,
        )
        if symbol.id not in {s.id for s in self.symbols}:
            self.symbols.append(symbol)
        body = _text(node)
        self.entries.append(
            EntryPoint(
                id=stable_id("ent", symbol.id, method, template),
                snapshot_id=self.ref.snapshot_id,
                kind=EntryPointKind.http_route,
                handler_symbol_id=symbol.id,
                method=method,
                path_template=template[:500],
                auth_dependencies=sorted(s for s in _AUTH_SIGNALS if s in body),
            )
        )

    @staticmethod
    def _named_exports(root: Node) -> dict[str, Node]:
        """`export function GET`, `export const GET = ...` and `export { h as GET }`."""
        out: dict[str, Node] = {}
        local: dict[str, Node] = {}
        for stmt in root.named_children:
            decl = (
                stmt.child_by_field_name("declaration") if stmt.type == "export_statement" else stmt
            )
            if decl is None:
                continue
            if decl.type in ("function_declaration", "generator_function_declaration"):
                name = _text(decl.child_by_field_name("name"))
                local[name] = decl
                if stmt.type == "export_statement":
                    out[name] = decl
            elif decl.type in ("lexical_declaration", "variable_declaration"):
                for d in decl.named_children:
                    if d.type == "variable_declarator":
                        name = _text(d.child_by_field_name("name"))
                        local[name] = d
                        if stmt.type == "export_statement":
                            out[name] = d
        for stmt in root.named_children:
            if stmt.type != "export_statement":
                continue
            for clause in stmt.named_children:
                if clause.type != "export_clause":
                    continue
                for spec in clause.named_children:
                    name = _text(spec.child_by_field_name("name"))
                    alias = _text(spec.child_by_field_name("alias")) or name
                    out[alias] = local.get(name, spec)
        return out

    @classmethod
    def _default_export(cls, root: Node) -> Node | None:
        for stmt in root.named_children:
            if stmt.type == "export_statement" and any(c.type == "default" for c in stmt.children):
                decl = stmt.child_by_field_name("declaration") or stmt.child_by_field_name("value")
                if decl is not None and decl.type == "identifier":
                    return cls._named_exports(root).get(_text(decl), stmt) or stmt
                return decl or stmt
            # CommonJS: module.exports = handler
            if stmt.type == "expression_statement":
                expr = stmt.named_children[0] if stmt.named_children else None
                if (
                    expr is not None
                    and expr.type == "assignment_expression"
                    and _text(expr.child_by_field_name("left")) == "module.exports"
                ):
                    return expr.child_by_field_name("right")
        return None

    def _express(self, file: SourceFile, root: Node) -> None:
        apps: set[str] = set()
        for node in _walk(root):
            if node.type == "variable_declarator":
                value = node.child_by_field_name("value")
                if value is not None and value.type == "call_expression":
                    callee = _text(value.child_by_field_name("function"))
                    if callee in ("express", "express.Router", "Router", "express.default"):
                        apps.add(_text(node.child_by_field_name("name")))
        if not apps:
            return
        for node in _walk(root):
            if node.type != "call_expression":
                continue
            fn = node.child_by_field_name("function")
            if fn is None or fn.type != "member_expression":
                continue
            obj, prop = (
                _text(fn.child_by_field_name("object")),
                _text(fn.child_by_field_name("property")),
            )
            args = node.child_by_field_name("arguments")
            if (
                obj not in apps
                or prop not in _EXPRESS_VERBS
                or args is None
                or not args.named_children
            ):
                continue
            first = args.named_children[0]
            if first.type != "string":
                if first.type == "template_string" or first.type == "identifier":
                    self.issues.append(
                        IndexIssue(
                            path=file.path,
                            reason=f"non-literal Express path at line {node.start_point[0] + 1}",
                        )
                    )
                continue
            path = _text(first)[1:-1]
            template = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", path)
            method = "ANY" if prop == "all" else prop.upper()
            self._emit(file, node, f"{prop}_{node.start_point[0] + 1}", method, template)

    def _cloud_functions(self, file: SourceFile, root: Node) -> None:
        for node in _walk(root):
            name = value = None
            if node.type == "variable_declarator" and node.parent is not None:
                if node.parent.parent is not None and node.parent.parent.type == "export_statement":
                    name, value = (
                        node.child_by_field_name("name"),
                        node.child_by_field_name("value"),
                    )
            elif node.type == "assignment_expression":
                left = _text(node.child_by_field_name("left"))
                if left.startswith("exports.") or left.startswith("module.exports."):
                    name, value = (
                        node.child_by_field_name("left"),
                        node.child_by_field_name("right"),
                    )
            if value is None or value.type != "call_expression":
                continue
            callee = _text(value.child_by_field_name("function"))
            if callee == "onRequest" or callee.endswith("https.onRequest"):
                export = _text(name).rsplit(".", 1)[-1]
                self._emit(file, value, export, "ANY", "/" + export)
