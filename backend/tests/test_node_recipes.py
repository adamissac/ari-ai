"""node_http recipe drafts (ADR-0023): rules parsing, the draft, and the connect job."""

from __future__ import annotations

import json

from test_build_recipes import FakeApp, _audit, _connect, _git
from test_build_recipes import github as github  # noqa: F401 - fixture

from backend import worker
from backend.node_recipes import draft_node, js_routes, owner_paths
from security_agents import node_recipe

RULES = """rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // A comment with braces {like} this must not confuse nesting.
    function isOwner(uid) {
      return request.auth != null && request.auth.uid == uid;
    }
    match /users/{uid} {
      allow read, write: if isOwner(uid);
      match /notes/{noteId} {
        allow read: if request.auth.uid == uid;
      }
    }
    match /profiles/{userId} {
      allow read: if request.auth != null;
    }
    match /teams/{teamId}/members/{memberId} {
      allow read: if memberId == request.auth.uid;
    }
    match /public/{doc=**} {
      allow read: if true;
    }
  }
}
"""

APP = {
    "package.json": json.dumps({"name": "x", "dependencies": {"firebase-admin": "13.10.0"},
                                "devDependencies": {"vitest": "2.1.9"}}),
    "package-lock.json": json.dumps({"packages": {"": {}}}),
    "firebase.json": json.dumps({"firestore": {"rules": "firestore.rules"}}),
    ".firebaserc": json.dumps({"projects": {"default": "acme-shop"}}),
    "firestore.rules": RULES,
    "api/status.js": (
        "export default function handler(req, res) {\n"
        "  if (req.method !== 'GET') return res.status(405).end();\n"
        "  const k = process.env.SHOP_SERVICE_ACCOUNT; const f = process.env.SHOP_FLAG;\n"
        "  return res.json({ ok: true });\n}\n"
    ),
    "api/orders/[id].js": "export default function handler(req, res) { if (req.method === 'GET') res.json({}); }\n",
    "api/hook.js": "export default function handler(req, res) { res.end(); }\n",
}  # fmt: skip


def test_owner_paths_follow_nesting_helpers_and_skip_non_owner_rules() -> None:
    assert owner_paths(RULES) == [
        "users/{uid}",
        "users/{uid}/notes/{noteId}",
        "teams/{teamId}/members/{uid}",
    ]


def test_draft_is_valid_and_only_includes_what_code_settles() -> None:
    files = {p: c for p, c in APP.items() if p.endswith(".js")}
    d = draft_node(APP.get, files, js_routes(files))
    assert d is not None
    r = d.recipe
    assert node_recipe.problems(r) == []
    assert r["firebase"]["project_id"] == "acme-shop"
    assert [p["path_template"] for p in r["firestore_paths"]] == owner_paths(RULES)
    assert r["serve"] == {"adapter": "vercel_functions", "dir": "api"}
    # Explicit-GET, parameterless routes only: ANY and {id} routes could not be checked honestly.
    assert [x["path_template"] for x in r["routes"]] == ["/api/status"]
    assert r["env"] == {"SHOP_SERVICE_ACCOUNT": "$sandbox_service_account"}
    assert r["test_command"] == {"runner": "vitest", "args": ["run"]}
    assert any("SHOP_FLAG" in n for n in d.notes) and any(
        "2 API route(s) left out" in n for n in d.notes
    )


def test_a_vitest_rules_config_is_the_test_command() -> None:
    app = {**APP, "vitest.rules.config.js": "export default {}\n"}
    files = {p: c for p, c in app.items() if p.startswith("api/")}
    r = draft_node(app.get, files, js_routes(files)).recipe
    assert r["test_command"] == {
        "runner": "vitest",
        "args": ["run", "--config", "vitest.rules.config.js"],
    }
    assert node_recipe.problems(r) == []


def test_no_lockfile_or_nothing_testable_means_no_draft() -> None:
    no_lock = {k: v for k, v in APP.items() if k != "package-lock.json"}
    assert draft_node(no_lock.get, {}, []) is None
    bare = {"package.json": "{}", "package-lock.json": "{}"}
    assert draft_node(bare.get, {}, []) is None


def test_connecting_a_firebase_js_repo_opens_a_node_recipe_pr(client_factory, github) -> None:  # noqa: F811
    bare = github(APP)
    _connect(client_factory("alice"))
    worker.drain(kinds=["propose_build_recipe"])
    [pr] = FakeApp.prs
    assert "Firestore emulators" in pr["body"] and "`users/{uid}`" in pr["body"]
    shown = json.loads(_git("show", f"{pr['head']}:build_recipe.json", cwd=bare))
    assert shown["kind"] == "node_http" and node_recipe.problems(shown) == []
    assert "deploy/sandbox_target.py" not in _git(
        "ls-tree", "-r", "--name-only", pr["head"], cwd=bare
    )
    opened = _audit("recipe.pr_opened")[0]
    assert opened["kind"] == "node_http" and opened["routes"] == ["api_status"]


def test_a_js_repo_with_nothing_testable_is_unsupported(client_factory, github) -> None:  # noqa: F811
    github({"package.json": "{}", "package-lock.json": "{}", "index.js": "console.log(1)\n"})
    _connect(client_factory("alice"))
    worker.drain(kinds=["propose_build_recipe"])
    assert FakeApp.prs == []
    assert "no Node app" in _audit("recipe.unsupported")[0]["reason"]
