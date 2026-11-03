"""The `node_http` build-recipe kind (ADR-0023).

The recipe is repository content: every field is validated here and nothing in it ever
reaches a shell. Identities are Firebase Auth-emulator users; their `auth_header` is
computed (an unsigned emulator ID token), never taken from the recipe.
"""

from __future__ import annotations

import base64
import json
import re
import time
from typing import Any

from .contracts import ErrorCode, PlatformError

KIND = "node_http"
ADAPTERS = ("vercel_functions", "next", "express_module")
TEST_RUNNERS = ("vitest", "jest")
PLACEHOLDERS = ("$sandbox_service_account",)
EMULATORS = ("auth", "firestore")

_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_UID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,29}$")
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_ENV_VALUE = re.compile(r"^[A-Za-z0-9 ._:/@-]{0,200}$")
_SECRETISH = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD|CREDENTIALS?)$|^GOOGLE_APPLICATION_CREDENTIALS$")
_DOC_PATH = re.compile(r"^[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)*$")
_PATH_TEMPLATE = re.compile(
    r"^(?:[A-Za-z0-9_-]+|\{[a-z][A-Za-z0-9_]*\})(?:/(?:[A-Za-z0-9_-]+|\{[a-z][A-Za-z0-9_]*\}))*$"
)
_ROUTE_PATH = re.compile(r"^/[A-Za-z0-9_./{}-]{0,200}$")
_REL = re.compile(r"^(?!/)(?!.*\.\.)[A-Za-z0-9_./-]{1,200}$")
_ARG = re.compile(r"^[A-Za-z0-9_./=:@-]{1,200}$")


def is_node(recipe: dict[str, Any]) -> bool:
    return recipe.get("kind") == KIND


def problems(recipe: dict[str, Any]) -> list[str]:
    """Every reason the recipe is not a valid node_http recipe (empty when it is)."""
    out: list[str] = []
    if recipe.get("recipe_version") != 1 or recipe.get("kind") != KIND:
        return ["recipe_version must be 1 and kind node_http"]
    if recipe.get("node", "22") not in ("20", "22"):
        out.append("node must be '20' or '22'")
    serve = recipe.get("serve")
    if serve is not None:
        if not isinstance(serve, dict) or serve.get("adapter") not in ADAPTERS:
            out.append(f"serve.adapter must be one of {list(ADAPTERS)}")
        elif any(not (isinstance(v, str) and _REL.match(v)) for k, v in serve.items() if k != "adapter"):
            out.append("serve fields must be safe relative paths or identifiers")
    env = recipe.get("env") or {}
    if not isinstance(env, dict) or len(env) > 40:
        out.append("env must be an object of at most 40 entries")
    else:
        for name, value in env.items():
            if not isinstance(name, str) or not _ENV_NAME.match(name):
                out.append(f"env name {name!r} is not allowed")
            elif value in PLACEHOLDERS:
                continue
            elif not isinstance(value, str) or not _ENV_VALUE.match(value):
                out.append(f"env {name}: value must be a plain literal or a platform placeholder")
            elif _SECRETISH.search(name):
                out.append(f"env {name}: secret-like names take a platform placeholder, never a literal")
    firebase = recipe.get("firebase")
    if firebase is not None:
        if not isinstance(firebase, dict) or not _PROJECT.match(str(firebase.get("project_id", ""))):
            out.append("firebase.project_id must be a Firebase project id")
        else:
            if not _REL.match(str(firebase.get("rules", "firestore.rules"))):
                out.append("firebase.rules must be a safe relative path")
            emulators = firebase.get("emulators", list(EMULATORS))
            if not isinstance(emulators, list) or not set(emulators) <= set(EMULATORS):
                out.append(f"firebase.emulators must be a subset of {list(EMULATORS)}")
    identities = recipe.get("identities")
    if not isinstance(identities, dict) or not 2 <= len(identities) <= 8:
        out.append("identities must name 2 to 8 fixture identities")
        identities = {}
    uids: set[str] = set()
    for name, spec in identities.items():
        if not _NAME.match(str(name)) or not isinstance(spec, dict):
            out.append(f"identity {name!r} is malformed")
            continue
        if "auth_header" in spec:
            out.append(f"identity {name}: auth_header is computed by the platform, not written")
        uid = str(spec.get("uid", ""))
        if not _UID.match(uid) or uid in uids:
            out.append(f"identity {name}: uid must be a unique [A-Za-z0-9_-]{{1,64}}")
        uids.add(uid)
        claims = spec.get("claims", {})
        if not isinstance(claims, dict) or len(json.dumps(claims)) > 1000:
            out.append(f"identity {name}: claims must be a small object")
    for item in recipe.get("seed") or []:
        if not isinstance(item, dict) or not _DOC_PATH.match(str(item.get("path", ""))):
            out.append("seed entries need a document path")
        elif str(item["path"]).count("/") % 2 != 1:
            out.append(f"seed path {item['path']!r} is not a document path")
        elif not isinstance(item.get("data"), dict) or len(json.dumps(item["data"])) > 10_000:
            out.append(f"seed {item['path']}: data must be an object under 10 kB")
    resources = recipe.get("resources") or {}
    if not isinstance(resources, dict):
        out.append("resources must be an object")
        resources = {}
    for kind, owners in resources.items():
        if not _NAME.match(str(kind)) or not isinstance(owners, dict):
            out.append(f"resource {kind!r} is malformed")
            continue
        for owner, res in owners.items():
            if owner not in identities or not isinstance(res, dict) or not _UID.match(str(res.get("id", ""))):
                out.append(f"resource {kind}/{owner}: owner must be an identity and id [A-Za-z0-9_-]{{1,64}}")
    ids: set[str] = set()
    for fp in recipe.get("firestore_paths") or []:
        if not isinstance(fp, dict) or not _NAME.match(str(fp.get("id", ""))) or fp["id"] in ids:
            out.append("firestore_paths entries need a unique snake_case id")
            continue
        ids.add(fp["id"])
        template = str(fp.get("path_template", ""))
        if not _PATH_TEMPLATE.match(template) or template.count("/") % 2 != 1 or "{uid}" not in template:
            out.append(f"firestore path {fp['id']}: path_template must be a document path containing {{uid}}")
    for route in recipe.get("routes") or []:
        if not isinstance(route, dict) or not _NAME.match(str(route.get("id", ""))):
            out.append("routes need a snake_case id")
        elif str(route.get("method", "GET")).upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            out.append(f"route {route['id']}: unknown method")
        elif not _ROUTE_PATH.match(str(route.get("path_template", ""))):
            out.append(f"route {route['id']}: path_template must start with /")
    test = recipe.get("test_command")
    if test is not None and (
        not isinstance(test, dict)
        or test.get("runner") not in TEST_RUNNERS
        or not isinstance(test.get("args", []), list)
        or not all(isinstance(a, str) and _ARG.match(a) for a in test.get("args", []))
    ):
        out.append(f"test_command needs a runner in {list(TEST_RUNNERS)} and plain args")
    if not recipe.get("routes") and not recipe.get("firestore_paths"):
        out.append("a node_http recipe needs routes or firestore_paths to test")
    return out


def _b64(obj: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":")).encode()).rstrip(b"=").decode()


def emulator_id_token(project_id: str, uid: str, spec: dict[str, Any], now: float | None = None) -> str:
    """An unsigned ID token: accepted only by the Auth emulator and by Admin SDKs pointed
    at it (FIREBASE_AUTH_EMULATOR_HOST). Worthless against a real Firebase project."""
    iat = int(now if now is not None else time.time())
    claims = {
        **(spec.get("claims") or {}),
        "iss": f"https://securetoken.google.com/{project_id}",
        "aud": project_id,
        "auth_time": iat,
        "user_id": uid,
        "sub": uid,
        "iat": iat,
        "exp": iat + 3600,
        "firebase": {"identities": {}, "sign_in_provider": "custom"},
    }
    if spec.get("email"):
        claims["email"] = spec["email"]
        claims["email_verified"] = bool(spec.get("email_verified", False))
    return _b64({"alg": "none", "typ": "JWT"}) + "." + _b64(claims) + "."


def resolved(recipe: dict[str, Any]) -> dict[str, Any]:
    """The validated recipe with each identity's computed `auth_header`. Fails closed."""
    issues = problems(recipe)
    if issues:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "node_http recipe: " + "; ".join(issues[:5]))
    project = (recipe.get("firebase") or {}).get("project_id", "demo-ari-sandbox")
    out = json.loads(json.dumps(recipe))
    for spec in out["identities"].values():
        spec["auth_header"] = "Bearer " + emulator_id_token(project, spec["uid"], spec)
    return out


def stack_config(recipe: dict[str, Any], *, serve: bool) -> dict[str, Any]:
    """Launcher config for `sandbox/node_stack.mjs` from a resolved recipe. `serve=False`
    starts only the Firestore emulator (rules checks); the driver adds ports and node_dir."""
    firebase = recipe.get("firebase") or {}
    emulators = list(firebase.get("emulators", list(EMULATORS))) if firebase else []
    if not serve:
        emulators = [e for e in emulators if e == "firestore"]
    return {
        "project_id": str(firebase.get("project_id", "demo-ari-sandbox")),
        "emulators": emulators,
        "identities": [
            {k: spec.get(k) for k in ("uid", "email", "email_verified", "claims") if k in spec}
            for spec in recipe["identities"].values()
        ],
        "seed": list(recipe.get("seed") or []) if serve else [],
        "env": dict(recipe.get("env") or {}) if serve else {},
        "serve": dict(recipe["serve"]) if serve and recipe.get("serve") else None,
    }


def test_command(recipe: dict[str, Any]) -> tuple[str, ...] | None:
    test = recipe.get("test_command")
    if not isinstance(test, dict):
        return None
    return (str(test["runner"]), *[str(a) for a in test.get("args", [])])
