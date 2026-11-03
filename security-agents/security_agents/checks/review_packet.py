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
ALLOWED_IMPORTS = frozenset(
    {"json", "decimal", "fastapi", "datetime", "pytest", "threading", "concurrent"}
)  # + the recipe's app_factory package
# Harness templates (ADR-0023) start exactly one reviewed support file and read its output.
HARNESS_IMPORTS = frozenset({"json", "os", "pathlib", "subprocess", "tempfile", "pytest"})
HARNESS_FORBIDDEN = ("socket", "os.system", "eval(", "exec(", "shell=True")
NODE_RECIPE: dict[str, Any] = {
    "recipe_version": 1,
    "kind": "node_http",
    "firebase": {"project_id": "demo-ari-sample", "rules": "firestore.rules"},
    "identities": {"alice": {"uid": "sbx-alice"}, "bob": {"uid": "sbx-bob"}},
    "firestore_paths": [{"id": "user_doc", "path_template": "users/{uid}"}],
}
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
    "firestore.owner_isolation@1": {
        "path_id": "user_doc",
        "owner_identity": "alice",
        "other_identity": "bob",
    },
    "firestore.unauthenticated_denied@1": {"path_id": "user_doc", "owner_identity": "alice"},
    "firestore.collection_enumeration@1": {
        "path_id": "user_doc",
        "owner_identity": "alice",
        "other_identity": "bob",
    },
    "input_validation.bounds@1": {
        "route_id": "create_refund",
        "read_route_id": "payment_detail",
        "owner_identity": "alice",
        "over_by": "1.00",
    },
    "input_validation.concurrent_bound@1": {
        "route_id": "create_refund",
        "read_route_id": "payment_detail",
        "owner_identity": "alice",
        "parallel": 8,
    },
    "input_validation.destination@1": {
        "route_id": "sample_payout",
        "read_route_id": "payment_detail",
        "owner_identity": "alice",
    },
}
# payments-lite has no route that names a destination; the packet renders the destination
# template against this illustrative one, added to the recipe for the packet only.
SAMPLE_ROUTES = [
    {
        "id": "sample_payout",
        "method": "POST",
        "path_template": "/payouts",
        "resource": "payment",
        "body_template": {"payment_id": "{resource_id}", "to": "{destination}", "amount": "{amount}"},
        "accumulated_field": "refunded",
    }
]
CHECKLIST = (
    "The rendered module imports only json, decimal, datetime, fastapi, pytest (to report a setup problem as skipped, never as a finding), threading and concurrent.futures (the race template) and the package named by the recipe's app_factory (validated as package.module:callable).",
    "It uses only fixture identities and resource ids declared in the build recipe.",
    "It opens no sockets, spawns no processes and reads no environment or files outside the workspace.",
    "Its assertions state the expectation, so a failure means the expectation did not hold.",
    "Its side effects match the declared side_effect_class.",
    "Harness templates only: the module starts the listed support file with `node` (no shell) and reads its JSON output; the support file reaches only the loopback Firestore emulator.",
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


def lib_node_recipe() -> dict[str, Any]:
    from .. import node_recipe

    return node_recipe.resolved({**NODE_RECIPE, "routes": []})


def packet(recipe_path: Path = RECIPE) -> list[dict[str, Any]]:
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    recipe["routes"] = [*recipe.get("routes", []), *SAMPLE_ROUTES]
    library = lib.default_library()
    entries = []
    for meta in library.templates.values():
        renderer = lib._RENDERERS[meta.ref]
        renderer_source = inspect.getsource(renderer)
        harness = bool(meta.support_files)
        sample_recipe = lib_node_recipe() if harness else recipe
        rendered = library.render(meta.ref, sample_recipe, SAMPLES[meta.ref])
        code = _code_only(rendered)
        imports = _imports(rendered)
        support = {f: (Path(lib.__file__).parent / f).read_text(encoding="utf-8") for f in meta.support_files}
        entries.append(
            {
                "ref": meta.ref,
                "category": meta.category,
                "side_effect_class": meta.side_effect_class,
                "reviewed_by": meta.reviewed_by,
                "parameters": list(meta.parameters),
                "renderer_sha256": _sha(
                    (
                        lib._FIRESTORE_PREAMBLE
                        + inspect.getsource(lib._firestore_params)
                        + inspect.getsource(lib._firestore_path)
                        + inspect.getsource(lib._firestore_identity)
                        + "".join(support.values())
                        if harness
                        else lib._PREAMBLE
                        + lib._PREAMBLE_HTTP
                        + inspect.getsource(lib.app_factory)
                        + inspect.getsource(lib._inprocess_preamble)
                    )
                    + renderer_source
                ),
                "sample_parameters": SAMPLES[meta.ref],
                "rendered_sha256": _sha(rendered),
                "imports": imports,
                "imports_within_allowlist": set(imports)
                <= (
                    HARNESS_IMPORTS
                    if harness
                    else ALLOWED_IMPORTS | {lib.app_factory(recipe)[0].split(".")[0]}
                ),
                "forbidden_tokens_found": [
                    t for t in (HARNESS_FORBIDDEN if harness else FORBIDDEN_TOKENS) if t in code
                ],
                "rendered": rendered,
                "support_files": support,
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
        for name, source in entry["support_files"].items():
            lines += [
                "",
                f"Support file `{name}` (reviewed with this template):",
                "",
                "```js",
                source.rstrip(),
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
