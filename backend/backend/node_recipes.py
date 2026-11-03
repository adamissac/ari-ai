"""Deterministic `node_http` build-recipe drafts for JavaScript/TypeScript repositories (ADR-0023).

Only what code reading settles goes in: the Vercel `api/` adapter and its explicit-GET
routes, Firestore paths whose rules tie a document to `request.auth.uid`, the test runner,
and a throwaway service account for env vars that name one. Fixture identities are two
synthetic Auth-emulator users. Everything is validated by `security_agents.node_recipe`
before a PR is proposed; the owner edits and merges it like the Python recipe.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

_MATCH = re.compile(r"match\s+(/\S+)\s*\{")
_WILDCARD = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)(?:=\*\*)?\}$")
_ENV = re.compile(r"process\.env\.([A-Z][A-Z0-9_]{0,63})")
_ACCOUNT_ENV = re.compile(r"SERVICE_ACCOUNT|CREDENTIAL")
_PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,29}$")

IDENTITIES = {
    "alice": {"uid": "sbx-alice", "email": "alice@sbx.test", "email_verified": True},
    "bob": {"uid": "sbx-bob", "email": "bob@sbx.test", "email_verified": True},
}


@dataclass
class NodeDraft:
    recipe: dict[str, Any]
    notes: list[str] = field(default_factory=list)


def owner_paths(rules: str) -> list[str]:
    """Document paths (as templates with `{uid}`) whose block compares a path wildcard with
    `request.auth.uid`, directly or through a one-argument helper such as `isOwner(uid)`."""
    rules = re.sub(r"//[^\n]*", "", rules)  # comments may hold braces
    owner_helpers = {
        name
        for name, _arg in re.findall(
            r"function\s+(\w+)\s*\(\s*(\w+)\s*\)\s*\{[^}]*request\.auth\.uid\s*==\s*\2", rules
        )
    }
    out: list[str] = []
    stack: list[tuple[list[str], int]] = []  # (segments, brace depth when opened)
    depth = 0
    i = 0
    while i < len(rules):
        m = _MATCH.match(rules, i)
        if m:
            parent = stack[-1][0] if stack else []
            segments = [s for s in m.group(1).strip("/").split("/") if s]
            stack.append((parent + segments, depth))
            depth += 1
            body_start = m.end()
            body = _block(rules, body_start)
            own = body.split("match ", 1)[0]  # the block's own rules, not nested matches
            full = stack[-1][0]
            if full[:3] == ["databases", "{database}", "documents"]:
                full = full[3:]
            wilds = {w.group(1): n for n, s in enumerate(full) if (w := _WILDCARD.match(s))}
            for var, index in wilds.items():
                direct = re.search(
                    rf"request\.auth\.uid\s*==\s*{var}\b|\b{var}\s*==\s*request\.auth\.uid", own
                )
                helper = any(re.search(rf"\b{h}\(\s*{var}\s*\)", own) for h in owner_helpers)
                if (direct or helper) and len(full) % 2 == 0:
                    path = "/".join(
                        "{uid}"
                        if n == index
                        else (
                            s if not _WILDCARD.match(s) else "{" + _WILDCARD.match(s).group(1) + "}"
                        )  # type: ignore[union-attr]
                        for n, s in enumerate(full)
                    )
                    if "**" not in path and path not in out:
                        out.append(path)
            i = body_start
            continue
        ch = rules[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if stack and stack[-1][1] == depth:
                stack.pop()
        i += 1
    return out


def _block(text: str, start: int) -> str:
    depth = 1
    for j in range(start, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[start:j]
    return text[start:]


def _snake(path: str) -> str:
    parts = [p for p in path.split("/") if not p.startswith("{")]
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", "_".join(parts)).lower()
    return re.sub(r"[^a-z0-9_]", "_", name)[:28] or "doc"


def draft_node(
    blob: Callable[[str], str | None], files: dict[str, str], routes: list[dict[str, Any]]
) -> NodeDraft | None:
    """A node_http draft, or None when the repository is not a Node app we can test.
    `routes` are the JS/TS entry points from code intelligence ({method, path_template, path})."""
    package = blob("package.json")
    if package is None or blob("package-lock.json") is None:
        return None
    try:
        pkg = json.loads(package)
    except ValueError:
        return None
    notes: list[str] = []
    recipe: dict[str, Any] = {
        "_comment": "Drafted by Ari (ADR-0023). Identities are Firebase Auth-emulator users; "
        "Ari computes their auth headers. Edit freely before merging.",
        "recipe_version": 1,
        "kind": "node_http",
        "node": "22",
        "identities": IDENTITIES,
    }
    firebase_json = blob("firebase.json")
    firebase: dict[str, Any] = {}
    if firebase_json is not None:
        try:
            firebase = json.loads(firebase_json)
        except ValueError:
            firebase = {}
    rules_path = str((firebase.get("firestore") or {}).get("rules") or "firestore.rules")
    rules = blob(rules_path)
    if firebase_json is not None or rules is not None:
        project = ""
        rc = blob(".firebaserc")
        if rc:
            try:
                project = str(json.loads(rc).get("projects", {}).get("default", ""))
            except ValueError:
                project = ""
        if not _PROJECT.match(project):
            project = "demo-ari-sandbox"
            notes.append("No valid default project in .firebaserc; using demo-ari-sandbox.")
        recipe["firebase"] = {
            "project_id": project,
            "rules": rules_path,
            "emulators": ["auth", "firestore"],
        }
    if rules is not None:
        paths = owner_paths(rules)
        ids: dict[str, int] = {}
        recipe["firestore_paths"] = []
        for path in paths[:12]:
            base = _snake(path)
            ids[base] = ids.get(base, 0) + 1
            fid = base if ids[base] == 1 else f"{base}_{ids[base]}"
            recipe["firestore_paths"].append({"id": fid, "path_template": path})
        notes.append(f"{len(paths)} owner-scoped Firestore paths found in `{rules_path}`.")
    vercel = [r for r in routes if str(r.get("path", "")).startswith("api/")]
    if vercel:
        recipe["serve"] = {"adapter": "vercel_functions", "dir": "api"}
        gets = [
            r for r in vercel if r.get("method") == "GET" and "{" not in str(r.get("path_template"))
        ]
        recipe["routes"] = [
            {
                "id": _snake(str(r["path_template"]).strip("/").replace("-", "_")) or "root",
                "method": "GET",
                "path_template": str(r["path_template"]),
            }
            for r in gets[:12]
        ]
        skipped = len(vercel) - len(gets)
        if skipped:
            notes.append(
                f"{skipped} API route(s) left out: no explicit GET, or a path parameter that needs a fixture "
                "resource. Add them with `resources` to have Probe check them."
            )
        names = sorted(
            {
                n
                for path, text in files.items()
                if path.startswith(("api/", "server/", "lib/"))
                for n in _ENV.findall(text)
            }
        )
        recipe["env"] = {n: "$sandbox_service_account" for n in names if _ACCOUNT_ENV.search(n)}
        other = [n for n in names if not _ACCOUNT_ENV.search(n)]
        if other:
            notes.append(
                f"Env vars the app reads and the draft leaves unset: {', '.join(other[:10])}."
            )
    elif any(str(r.get("path", "")).endswith(("route.ts", "route.js")) for r in routes):
        notes.append(
            "Next.js routes are not served yet (ADR-0023); only Firestore rules are tested."
        )
    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    runner = "vitest" if "vitest" in deps else "jest" if "jest" in deps else None
    if runner:
        recipe["test_command"] = {"runner": runner, "args": ["run"] if runner == "vitest" else []}
    if not recipe.get("routes") and not recipe.get("firestore_paths"):
        return None
    return NodeDraft(recipe=recipe, notes=notes)


def js_routes(files: dict[str, str]) -> list[dict[str, Any]]:
    """JS/TS HTTP entry points via code intelligence's syntactic detector."""
    from pathlib import PurePosixPath

    from code_intelligence.js_routes import JsRouteExtractor
    from code_intelligence.models import SourceFile
    from shared.intelligence import SnapshotRef

    lang = {".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
            ".ts": "typescript", ".tsx": "typescript"}  # fmt: skip
    ref = SnapshotRef(
        project_id="prj_recipedraft", repo_id="rep_recipedraft", snapshot_id="snp_recipedraft",
        commit_sha="0" * 40, index_version="recipe-draft",
    )  # fmt: skip
    sources = [
        SourceFile(
            path=p,
            blob_sha="0",
            content_sha256="0",
            language=lang[PurePosixPath(p).suffix],
            is_test=False,
            content=c,
        )  # fmt: skip
        for p, c in files.items()
        if PurePosixPath(p).suffix in lang
    ]
    extractor = JsRouteExtractor(ref, sources)
    extractor.extract()
    paths = {s.id: s.path for s in extractor.symbols}
    return [
        {"method": e.method, "path_template": e.path_template, "path": paths[e.handler_symbol_id]}
        for e in extractor.entries
    ]


def node_pr_body(d: NodeDraft) -> str:
    r = d.recipe
    routes = "\n".join(f"- `GET {x['path_template']}`" for x in r.get("routes", [])) or "- none"
    paths = "\n".join(f"- `{x['path_template']}`" for x in r.get("firestore_paths", [])) or "- none"
    notes = "\n".join(f"- {n}" for n in d.notes) or "- none"
    return (
        "Ari runs its security agents on every pushed commit. For this JavaScript app they run "
        "it in an isolated sandbox against the Firebase Auth and Firestore emulators (never your "
        "real project), and this `build_recipe.json` tells them how.\n\n"
        f"HTTP routes Probe may check for authentication:\n{routes}\n\n"
        f"Firestore paths whose rules Probe may check for cross-user access:\n{paths}\n\n"
        "The fixture identities are two synthetic emulator users. Credentials the app needs are "
        "throwaway service accounts generated per run.\n\n"
        f"Notes:\n{notes}\n\nDrafted from code analysis. Edit freely before merging; close the PR to opt out."
    )
