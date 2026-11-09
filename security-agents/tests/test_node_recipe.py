"""node_http recipe validation and emulator identities (ADR-0023)."""

import base64
import json

import pytest

from security_agents import node_recipe
from security_agents.contracts import PlatformError


def recipe(**changes):
    base = {
        "recipe_version": 1,
        "kind": "node_http",
        "node": "22",
        "serve": {"adapter": "vercel_functions", "dir": "api"},
        "env": {
            "PYPATH_SCHOOL_CODE_CHECKS": "enabled",
            "PYPATH_FIREBASE_SERVICE_ACCOUNT": "$sandbox_service_account",
        },
        "firebase": {
            "project_id": "mypypath",
            "rules": "firestore.rules",
            "emulators": ["auth", "firestore"],
        },
        "identities": {
            "alice": {"uid": "sbx-alice", "email": "alice@sbx.test", "email_verified": True},
            "bob": {"uid": "sbx-bob", "claims": {"role": "student"}},
        },
        "seed": [{"path": "users/sbx-alice", "data": {"role": "teacher"}}],
        "firestore_paths": [{"id": "user_doc", "path_template": "users/{uid}"}],
        "routes": [{"id": "teacher_status", "method": "GET", "path_template": "/api/teacher-verification"}],
        "test_command": {"runner": "vitest", "args": ["run", "tests/rules"]},
    }
    base.update(changes)
    return base


def test_valid_recipe_has_no_problems():
    assert node_recipe.problems(recipe()) == []


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        ({"kind": "python_asgi"}, "kind node_http"),
        ({"serve": {"adapter": "npm run dev"}}, "serve.adapter"),
        ({"serve": {"adapter": "express_module", "module": "../../etc/passwd"}}, "safe relative"),
        ({"env": {"API_KEY": "sk-live-123"}}, "secret-like"),
        ({"env": {"NODE_OPTIONS": "--require /tmp/x.js; rm -rf /"}}, "plain literal"),
        ({"env": {"lower": "x"}}, "env name"),
        ({"firebase": {"project_id": "X"}}, "project_id"),
        ({"firebase": {"project_id": "mypypath", "emulators": ["functions"]}}, "emulators"),
        ({"identities": {"alice": {"uid": "a"}}}, "2 to 8"),
        ({"identities": {"alice": {"uid": "a"}, "bob": {"uid": "a"}}}, "unique"),
        ({"identities": {"alice": {"uid": "a", "auth_header": "Bearer x"}, "bob": {"uid": "b"}}}, "computed"),
        ({"seed": [{"path": "users", "data": {}}]}, "not a document path"),
        ({"firestore_paths": [{"id": "x", "path_template": "users/alice"}]}, "{uid}"),
        ({"firestore_paths": [{"id": "x", "path_template": "users/{uid}/code"}]}, "{uid}"),
        ({"routes": [{"id": "r", "path_template": "api/x"}]}, "start with /"),
        ({"test_command": {"runner": "sh", "args": ["-c", "curl evil"]}}, "test_command"),
        ({"test_command": {"runner": "vitest", "args": ["run; curl evil"]}}, "test_command"),
        ({"routes": [], "firestore_paths": []}, "routes or firestore_paths"),
    ],
)
def test_invalid_recipes_are_refused(change, fragment):
    issues = node_recipe.problems(recipe(**change))
    assert any(fragment in i for i in issues), issues


def _claims(header):
    token = header.removeprefix("Bearer ")
    head, body, sig = token.split(".")
    pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
    return (
        json.loads(base64.urlsafe_b64decode(pad(head))),
        json.loads(base64.urlsafe_b64decode(pad(body))),
        sig,
    )


def test_resolved_identities_carry_unsigned_emulator_tokens():
    out = node_recipe.resolved(recipe())
    head, body, sig = _claims(out["identities"]["alice"]["auth_header"])
    assert head == {"alg": "none", "typ": "JWT"} and sig == ""
    assert body["sub"] == "sbx-alice" and body["aud"] == "mypypath"
    assert body["email"] == "alice@sbx.test" and body["email_verified"] is True
    _, bob, _ = _claims(out["identities"]["bob"]["auth_header"])
    assert bob["role"] == "student" and "email" not in bob
    # Registered claims always win over recipe claims.
    sneaky = recipe(
        identities={"alice": {"uid": "sbx-alice", "claims": {"sub": "admin"}}, "bob": {"uid": "b"}}
    )
    assert (
        _claims(node_recipe.resolved(sneaky)["identities"]["alice"]["auth_header"])[1]["sub"] == "sbx-alice"
    )


def test_resolved_fails_closed():
    with pytest.raises(PlatformError):
        node_recipe.resolved(recipe(env={"SECRET_TOKEN": "abc"}))


def test_a_node_recipe_is_not_read_as_tampered_pytest_config(tmp_path):
    """Verify rejected every patch in the live mypypath run: the dict test_command looked unreadable."""
    import shutil

    from security_agents.tools.services import PatchApplier

    snap, patched = tmp_path / "snap", tmp_path / "patched"
    snap.mkdir()
    (snap / "build_recipe.json").write_text(json.dumps(recipe()))
    (snap / "firestore.rules").write_text("allow read: if true;\n")
    shutil.copytree(snap, patched)
    (patched / "firestore.rules").write_text("allow read: if false;\n")
    diff = (
        "diff --git a/firestore.rules b/firestore.rules\n--- a/firestore.rules\n+++ b/firestore.rules\n"
        "@@ -1 +1 @@\n-allow read: if true;\n+allow read: if false;\n"
    )
    assert PatchApplier._tampered_runner_config(diff, snap, patched) == []
    bad = {**recipe(), "test_command": {"runner": "mocha", "args": []}}
    (snap / "build_recipe.json").write_text(json.dumps(bad))
    assert PatchApplier._tampered_runner_config(diff, snap, patched)  # still fails closed
