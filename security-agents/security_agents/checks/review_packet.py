from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any

from . import library as lib

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
RECIPE = PACKAGE_ROOT.parent / "examples" / "payments-lite" / "build_recipe.json"
ALLOWED_IMPORTS = frozenset({"json", "decimal", "fastapi", "datetime"})  # + the recipe's app_factory package
FORBIDDEN_TOKENS = ("subprocess", "socket", "http://", "https://", "requests.", "os.system", "eval(", "exec(")
SAMPLES: dict[str, dict[str, Any]] = {
    "access_control.ownership@1": {
        "route_id": "payment_detail",
        "owner_identity": "alice",
        "other_identity": "bob",
    },
    "access_control.authentication@1": {
        "route_id": "payment_detail",
        "identity": "alice",
    },
    "access_control.role@1": {
        "route_id": "create_refund",
        "restricted_identity": "bob",
        "permitted_identity": "alice",
    },
    "input_validation.bounds@1": {
        "route_id": "create_refund",
        "read_route_id": "payment_detail",
        "owner_identity": "alice",
        "over_by": "1.00",
    },
}
CHECKLIST = (
    "The rendered module imports only json, decimal, datetime, fastapi and the package named by the recipe's app_factory (validated as package.module:callable).",
    "It uses only fixture identities and resource ids declared in the build recipe.",
    "It opens no sockets, spawns no processes and reads no environment or files outside the workspace.",
    "Its assertions state the expectation, so a failure means the expectation did not hold.",
    "Its side effects match the declared side_effect_class.",
    "The renderer rejects unknown or missing parameters and identical owner and other identities.",
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _imports(source: str) -> list[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return sorted(found)


def _code_only(source: str) -> str:
    tree = ast.parse(source)
    body = tree.body[1:] if ast.get_docstring(tree) else tree.body
    return "\n".join(ast.unparse(node) for node in body)


def packet(recipe_path: Path = RECIPE) -> list[dict[str, Any]]:
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    library = lib.default_library()
    entries = []
    for meta in library.templates.values():
        renderer = lib._RENDERERS[meta.ref]
        renderer_source = inspect.getsource(renderer)
        rendered = library.render(meta.ref, recipe, SAMPLES[meta.ref])
        code = _code_only(rendered)
        imports = _imports(rendered)
        entries.append(
            {
                "ref": meta.ref,
                "category": meta.category,
                "side_effect_class": meta.side_effect_class,
                "reviewed_by": meta.reviewed_by,
                "parameters": list(meta.parameters),
                "renderer_sha256": _sha(
                    lib._PREAMBLE
                    + lib._PREAMBLE_HTTP
                    + inspect.getsource(lib.app_factory)
                    + inspect.getsource(lib._inprocess_preamble)
                    + renderer_source
                ),
                "sample_parameters": SAMPLES[meta.ref],
                "rendered_sha256": _sha(rendered),
                "imports": imports,
                "imports_within_allowlist": set(imports)
                <= ALLOWED_IMPORTS | {lib.app_factory(recipe)[0].split(".")[0]},
                "forbidden_tokens_found": [t for t in FORBIDDEN_TOKENS if t in code],
                "rendered": rendered,
            }
        )
    return entries


def render_markdown(entries: list[dict[str, Any]]) -> str:
    lines = [
        "# Probe check template review packet",
        "",
        "A human security owner signs off by replacing `reviewed_by` in",
        "`security_agents/checks/library.py` with their identity and recording the",
        "`renderer_sha256` they reviewed. Any change to a renderer changes its hash and needs a new review.",
        "",
        "Checklist for each template:",
        "",
        *[f"- [ ] {item}" for item in CHECKLIST],
    ]
    for entry in entries:
        lines += [
            "",
            f"## {entry['ref']}",
            "",
            f"- category: `{entry['category']}`; side effects: `{entry['side_effect_class']}`",
            f"- current reviewed_by: `{entry['reviewed_by']}`",
            f"- parameters: {', '.join(entry['parameters'])}",
            f"- renderer_sha256: `{entry['renderer_sha256']}`",
            f"- sample parameters: `{json.dumps(entry['sample_parameters'], sort_keys=True)}`",
            f"- rendered_sha256 (sample): `{entry['rendered_sha256']}`",
            f"- imports: {', '.join(entry['imports'])} (within allowlist: {entry['imports_within_allowlist']})",
            f"- forbidden tokens in code: {entry['forbidden_tokens_found'] or 'none'}",
            "",
            "```python",
            entry["rendered"].rstrip(),
            "```",
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="security_agents.checks.review_packet")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    entries = packet()
    text = render_markdown(entries)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)
    clean = all(e["imports_within_allowlist"] and not e["forbidden_tokens_found"] for e in entries)
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
