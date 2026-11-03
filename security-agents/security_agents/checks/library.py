"""Check-template library v0 (SEC-005).

A check template is a *reviewed, parameterised assertion test*. It does not
improvise: Probe (and Verify's re-check) may only pick a template id and fill
its typed parameters, which are validated against the target's scope-approved
`build_recipe.json` (route ids, fixture identity names, resource ids). The
template renders an ordinary pytest file that drives the target through its
normal API with synthetic fixture identities and compares the observed access
decision with the linked behavioural expectation. Rendered tests are read-only
with respect to anything outside the ephemeral target.

`matches_expectation` is computed from the executed test outcome, never from
model text. A template with `reviewed_by=None` is not runnable and the tool
fails closed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from ..contracts import ErrorCode, PlatformError

SideEffectClass = Literal["read_only", "ephemeral_target_only"]


@dataclass(frozen=True)
class CheckTemplateMeta:
    template_id: str
    version: str
    category: str
    description: str
    side_effect_class: SideEffectClass
    expectation_kinds: tuple[str, ...]
    parameters: tuple[str, ...]
    reviewed_by: str | None = None  # security-owner sign-off; None => not runnable
    support_files: tuple[str, ...] = ()  # reviewed files beside this module, copied into .sandbox/

    @property
    def ref(self) -> str:
        return f"{self.template_id}@{self.version}"

    def public(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "version": self.version,
            "ref": self.ref,
            "category": self.category,
            "description": self.description,
            "side_effect_class": self.side_effect_class,
            "expectation_kinds": list(self.expectation_kinds),
            "parameters": list(self.parameters),
            "runnable": self.reviewed_by is not None,
        }


# --------------------------------------------------------------------------- recipe access


def _route(recipe: dict[str, Any], route_id: str) -> dict[str, Any]:
    for route in recipe.get("routes", []):
        if route.get("id") == route_id:
            return route
    valid = sorted(str(r.get("id")) for r in recipe.get("routes", []))
    raise PlatformError(
        ErrorCode.SCHEMA_INVALID,
        f"route_id {route_id!r} is not in the build recipe; valid route ids: {', '.join(valid)}",
    )


def _identity(recipe: dict[str, Any], name: str) -> str:
    ident = recipe.get("identities", {}).get(name)
    if not ident or "auth_header" not in ident:
        valid = sorted(recipe.get("identities", {}))
        raise PlatformError(
            ErrorCode.SCHEMA_INVALID,
            f"identity {name!r} is not in the build recipe; valid identities: {', '.join(valid)}",
        )
    return str(ident["auth_header"])


def _resource_id(recipe: dict[str, Any], kind: str, owner: str) -> str:
    entry = recipe.get("resources", {}).get(kind, {}).get(owner)
    if not entry or "id" not in entry:
        owners = sorted(recipe.get("resources", {}).get(kind, {}))
        raise PlatformError(
            ErrorCode.SCHEMA_INVALID,
            f"resource {kind!r} for identity {owner!r} is not in the build recipe; "
            f"identities owning a {kind}: {', '.join(owners)}",
        )
    return str(entry["id"])


def _resource_amount(recipe: dict[str, Any], kind: str, owner: str) -> str:
    """Declared amount of a fixture resource, as the decimal string the API uses."""
    entry = recipe.get("resources", {}).get(kind, {}).get(owner, {})
    amount = entry.get("amount")
    if amount is None:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, f"resource {kind}/{owner} has no amount")
    try:
        Decimal(str(amount))
    except InvalidOperation as exc:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, f"amount {amount!r} is not a decimal") from exc
    return str(amount)


_PREAMBLE = '''"""Generated check: {ref}
Rendered by security_agents.checks.library from reviewed template parameters.
Target is driven in-process through its own app factory; no sockets are opened.
"""

import json
from decimal import Decimal

from fastapi.testclient import TestClient

{app_import}

RESULT = {{}}


def _client():
    return TestClient(create_app())
'''


_APP_FACTORY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*):([A-Za-z_][A-Za-z0-9_]*)$")
DEFAULT_APP_FACTORY = "payments_lite.app:create_app"


def app_factory(recipe: dict[str, Any]) -> tuple[str, str]:
    """(module, callable) of the recipe's ``app_factory``. The recipe comes from the
    customer's repository, so only a dotted module path and an identifier are accepted:
    nothing else from it ever reaches the rendered check's source."""
    raw = str(recipe.get("app_factory") or DEFAULT_APP_FACTORY)
    m = _APP_FACTORY.match(raw)
    if m is None:
        raise PlatformError(
            ErrorCode.SCHEMA_INVALID, f"app_factory {raw!r} must be 'package.module:callable'"
        )
    return m.group(1), m.group(2)


def _inprocess_preamble(ref: str, recipe: dict[str, Any]) -> str:
    module, factory = app_factory(recipe)
    line = f"from {module} import {factory}" + ("" if factory == "create_app" else " as create_app")
    return _PREAMBLE.format(ref=ref, app_import=line)


_PREAMBLE_HTTP = '''"""Generated check: {ref}
Rendered by security_agents.checks.library from reviewed template parameters.
Target is reached over HTTP at SANDBOX_TARGET_URL on the per-run internal network.
"""

import json
import os
import time
from decimal import Decimal

import httpx

RESULT = {{}}


def _client():
    base = os.environ["SANDBOX_TARGET_URL"]
    deadline = time.monotonic() + 30
    while True:
        try:
            httpx.get(base + "/", timeout=2)
            break
        except httpx.TransportError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)
    return httpx.Client(base_url=base, timeout=10)
'''

TRANSPORTS = ("inprocess", "http")


# --------------------------------------------------------------------------- templates


_PATH_PARAM = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


def _fill_path(template: str, resource_id: str) -> str:
    """Bind the route's single path parameter (``{id}`` or ``{payment_id}``) to the fixture id."""
    if len(_PATH_PARAM.findall(template)) != 1:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "route must have exactly one path parameter")
    return _PATH_PARAM.sub(lambda _: resource_id, template)


def _render_ownership(recipe: dict[str, Any], params: dict[str, Any]) -> str:
    """Owner keeps access; a different fixture identity is denied the same resource."""
    route = _route(recipe, str(params["route_id"]))
    kind = str(route["resource"])
    owner, other = str(params["owner_identity"]), str(params["other_identity"])
    if owner == other:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "owner_identity and other_identity must differ")
    path = _fill_path(str(route["path_template"]), _resource_id(recipe, kind, owner))
    method = str(route.get("method", "GET")).lower()
    if method != "get":
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "ownership template covers read routes only")
    denied = [int(c) for c in params.get("expected_denied_status", [403, 404])]
    return (
        _inprocess_preamble(str(params["_ref"]), recipe)
        + f"""

PATH = {path!r}
OWNER_HEADERS = {{"Authorization": {_identity(recipe, owner)!r}}}
OTHER_HEADERS = {{"Authorization": {_identity(recipe, other)!r}}}
DENIED = {denied!r}


def test_owner_retains_access():
    resp = _client().get(PATH, headers=OWNER_HEADERS)
    RESULT["owner_status"] = resp.status_code
    assert resp.status_code == 200, f"owner lost legitimate access: {{resp.status_code}}"


def test_other_identity_is_denied():
    resp = _client().get(PATH, headers=OTHER_HEADERS)
    RESULT["other_status"] = resp.status_code
    RESULT["other_leaked_body"] = resp.status_code == 200
    assert resp.status_code in DENIED, (
        f"expected one of {{DENIED}} for a non-owner, observed {{resp.status_code}}"
    )
"""
    )


def _render_bounds(recipe: dict[str, Any], params: dict[str, Any]) -> str:
    """The documented amount bound holds: an in-bounds request succeeds, a request
    that would push the accumulated total past the bound is rejected, and the
    accumulated total never exceeds the bound."""
    create = _route(recipe, str(params["route_id"]))
    read = _route(recipe, str(params["read_route_id"]))
    owner = str(params["owner_identity"])
    if str(create.get("method", "")).upper() != "POST":
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "bounds template needs a POST create route")
    body_template = create.get("body_template")
    if not isinstance(body_template, dict):
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "create route has no body_template")
    kind = str(create["resource"])
    resource_id = _resource_id(recipe, kind, owner)
    bound = _resource_amount(recipe, kind, owner)
    accumulated_field = str(create.get("accumulated_field") or "")
    if not accumulated_field:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "create route has no accumulated_field")
    read_path = _fill_path(str(read["path_template"]), resource_id)
    over_by = str(params.get("over_by", "1.00"))
    try:
        step = Decimal(over_by)
    except InvalidOperation as exc:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, f"over_by {over_by!r} is not a decimal") from exc
    if step <= 0:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "over_by must be positive")

    def body_for(amount: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in body_template.items():
            if value == "{resource_id}":
                out[key] = resource_id
            elif value == "{amount}":
                out[key] = amount
            else:
                out[key] = value
        return out

    full = str(Decimal(bound))
    extra = str(step)
    return (
        _inprocess_preamble(str(params["_ref"]), recipe)
        + f'''

CREATE_PATH = {str(create["path_template"])!r}
READ_PATH = {read_path!r}
HEADERS = {{"Authorization": {_identity(recipe, owner)!r}}}
BOUND = Decimal({full!r})
ACCUMULATED_FIELD = {accumulated_field!r}
FULL_BODY = {body_for(full)!r}
EXTRA_BODY = {body_for(extra)!r}


def test_in_bounds_request_is_accepted():
    """A refund up to the bound is legitimate and must still work."""
    resp = _client().post(CREATE_PATH, json=FULL_BODY, headers=HEADERS)
    RESULT["in_bounds_status"] = resp.status_code
    assert resp.status_code < 400, f"legitimate in-bounds request rejected: {{resp.status_code}}"


def test_bound_is_enforced_across_requests():
    client = _client()
    first = client.post(CREATE_PATH, json=FULL_BODY, headers=HEADERS)
    RESULT["first_status"] = first.status_code
    assert first.status_code < 400, f"setup request rejected: {{first.status_code}}"
    second = client.post(CREATE_PATH, json=EXTRA_BODY, headers=HEADERS)
    RESULT["over_bound_status"] = second.status_code
    detail = client.get(READ_PATH, headers=HEADERS)
    accumulated = Decimal(str(detail.json()[ACCUMULATED_FIELD]))
    RESULT["accumulated"] = str(accumulated)
    RESULT["bound"] = str(BOUND)
    assert 400 <= second.status_code < 500, (
        f"expected 4xx once the accumulated total would exceed {{BOUND}}, "
        f"observed {{second.status_code}}"
    )
    assert accumulated <= BOUND, (
        f"invariant broken: accumulated {{accumulated}} exceeds the bound {{BOUND}}"
    )
'''
    )


OWNERSHIP = CheckTemplateMeta(
    template_id="access_control.ownership",
    version="1",
    category="access_control.ownership",
    description=(
        "Confirm a resource owned by one fixture identity is not readable by another, while the "
        "owner keeps legitimate access. Parameters: route_id, owner_identity, other_identity."
    ),
    side_effect_class="read_only",
    expectation_kinds=("access_control",),
    parameters=("route_id", "owner_identity", "other_identity"),
    reviewed_by="security-owner:pending-human-signoff",
)

BOUNDS = CheckTemplateMeta(
    template_id="input_validation.bounds",
    version="1",
    category="input_validation.bounds",
    description=(
        "Confirm a documented amount bound is enforced across requests: an in-bounds request "
        "succeeds, a further request that would push the accumulated total past the bound is "
        "rejected 4xx, and the accumulated total never exceeds the bound. "
        "Parameters: route_id (POST create route), read_route_id, owner_identity, over_by."
    ),
    side_effect_class="ephemeral_target_only",
    expectation_kinds=("business_rule", "invariant", "input_validation"),
    parameters=("route_id", "read_route_id", "owner_identity", "over_by"),
    reviewed_by="security-owner:pending-human-signoff",
)


def _render_authentication(recipe: dict[str, Any], params: dict[str, Any]) -> str:
    """A protected route denies an unauthenticated request while a valid fixture
    identity retains access. Covers missing-authn/missing-authz changes."""
    route = _route(recipe, str(params["route_id"]))
    identity = str(params["identity"])
    method = str(route.get("method", "GET")).lower()
    if method != "get":
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "authentication template covers read routes only")
    path_template = str(route["path_template"])
    path_params = _PATH_PARAM.findall(path_template)
    if path_params:
        if len(path_params) != 1:
            raise PlatformError(ErrorCode.SCHEMA_INVALID, "route must have at most one path parameter")
        kind = str(route.get("resource") or "")
        if not kind:
            raise PlatformError(ErrorCode.SCHEMA_INVALID, "path-parametrized route has no resource kind")
        path = _fill_path(path_template, _resource_id(recipe, kind, identity))
    else:
        path = path_template
    denied = [int(c) for c in params.get("expected_denied_status", [401, 403])]
    return (
        _inprocess_preamble(str(params["_ref"]), recipe)
        + f"""

PATH = {path!r}
AUTH_HEADERS = {{"Authorization": {_identity(recipe, identity)!r}}}
DENIED = {denied!r}


def test_unauthenticated_request_is_denied():
    resp = _client().get(PATH)
    RESULT["anon_status"] = resp.status_code
    RESULT["anon_leaked_body"] = resp.status_code == 200
    assert resp.status_code in DENIED, (
        f"expected one of {{DENIED}} for an unauthenticated request, observed {{resp.status_code}}"
    )


def test_authenticated_identity_retains_access():
    resp = _client().get(PATH, headers=AUTH_HEADERS)
    RESULT["identity_status"] = resp.status_code
    assert resp.status_code < 400, (
        f"authenticated identity lost legitimate access: {{resp.status_code}}"
    )
"""
    )


AUTHENTICATION = CheckTemplateMeta(
    template_id="access_control.authentication",
    version="1",
    category="access_control.authentication",
    description=(
        "Confirm a protected route denies an unauthenticated request (401/403) while a valid "
        "fixture identity retains access. Parameters: route_id, identity."
    ),
    side_effect_class="read_only",
    expectation_kinds=("access_control", "authentication"),
    parameters=("route_id", "identity"),
    reviewed_by="security-owner:pending-human-signoff",
)

_MUTATING = {"POST", "PATCH", "PUT", "DELETE"}
_EXPIRY_PLACEHOLDER = re.compile(r"^\{expires_in_days:(\d{1,3})\}$")
_RESOURCE_KIND = re.compile(r"^\{resource:([A-Za-z_][A-Za-z0-9_]*)\}$")


def _render_role(recipe: dict[str, Any], params: dict[str, Any]) -> str:
    """A role-restricted mutating route denies a lower-privileged fixture identity while a
    permitted one keeps access. Covers missing/relaxed role checks (viewer→member, member→owner)."""
    route = _route(recipe, str(params["route_id"]))
    method = str(route.get("method", "GET")).upper()
    if method not in _MUTATING:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "role template needs a mutating route")
    permitted, restricted = str(params["permitted_identity"]), str(params["restricted_identity"])
    if permitted == restricted:
        raise PlatformError(
            ErrorCode.SCHEMA_INVALID, "permitted_identity and restricted_identity must differ"
        )
    kind = str(route.get("resource") or "")
    path_template = str(route["path_template"])
    path_params = _PATH_PARAM.findall(path_template)
    if len(path_params) > 1:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "route must have at most one path parameter")
    # The path resource belongs to the permitted identity (e.g. alice's project/finding); the
    # restricted identity must be turned away *before* any state change on it.
    path = _fill_path(path_template, _resource_id(recipe, kind, permitted)) if path_params else path_template
    body_template = route.get("body_template") or {}
    if not isinstance(body_template, dict):
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "route body_template must be an object")

    def src_for(tpl: Any) -> str:
        if isinstance(tpl, dict):
            return "{" + ", ".join(f"{k!r}: {src_for(v)}" for k, v in tpl.items()) + "}"
        if isinstance(tpl, list):
            return "[" + ", ".join(src_for(v) for v in tpl) + "]"
        if (m := _EXPIRY_PLACEHOLDER.match(str(tpl))) is not None:
            return f"_expires({m.group(1)})"
        if (m := _RESOURCE_KIND.match(str(tpl))) is not None:
            return repr(_resource_id(recipe, m.group(1), permitted))
        if tpl == "{resource_id}":
            return repr(_resource_id(recipe, kind, permitted))
        if tpl == "{amount}":
            return repr(_resource_amount(recipe, kind, permitted))
        return repr(tpl)

    def uses_expiry(tpl: Any) -> bool:
        if isinstance(tpl, dict):
            return any(uses_expiry(v) for v in tpl.values())
        if isinstance(tpl, list):
            return any(uses_expiry(v) for v in tpl)
        return _EXPIRY_PLACEHOLDER.match(str(tpl)) is not None

    needs_expiry_helper = uses_expiry(body_template)
    body_src = src_for(body_template)
    denied = [int(c) for c in params.get("expected_denied_status", [401, 403, 404])]
    helper = (
        """
def _expires(days):
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
"""
        if needs_expiry_helper
        else ""
    )
    return (
        _inprocess_preamble(str(params["_ref"]), recipe)
        + f"""

PATH = {path!r}
METHOD = {method.lower()!r}
BODY = {body_src}
RESTRICTED_HEADERS = {{"Authorization": {_identity(recipe, restricted)!r}}}
PERMITTED_HEADERS = {{"Authorization": {_identity(recipe, permitted)!r}}}
DENIED = {denied!r}
"""
        + helper
        + """

def test_restricted_identity_is_denied():
    resp = _client().request(METHOD, PATH, json=BODY, headers=RESTRICTED_HEADERS)
    RESULT["restricted_status"] = resp.status_code
    RESULT["restricted_leaked_or_mutated"] = resp.status_code < 400
    assert resp.status_code in DENIED, (
        f"expected one of {DENIED} for a lower-privileged identity, "
        f"observed {resp.status_code}"
    )


def test_permitted_identity_retains_access():
    resp = _client().request(METHOD, PATH, json=BODY, headers=PERMITTED_HEADERS)
    RESULT["permitted_status"] = resp.status_code
    assert resp.status_code < 400, (
        f"permitted identity lost legitimate access: {resp.status_code}"
    )
"""
    )


ROLE = CheckTemplateMeta(
    template_id="access_control.role",
    version="1",
    category="access_control.role",
    description=(
        "Confirm a role-restricted mutating route (POST/PATCH/PUT/DELETE) denies a "
        "lower-privileged fixture identity (401/403/404) while a permitted one keeps access. "
        "Parameters: route_id, restricted_identity, permitted_identity."
    ),
    side_effect_class="ephemeral_target_only",
    expectation_kinds=("access_control", "authorization", "role"),
    parameters=("route_id", "restricted_identity", "permitted_identity"),
    reviewed_by="security-owner:pending-human-signoff",
)

# --------------------------------------------------------------------------- Firestore rules (ADR-0023)

_FIRESTORE_PREAMBLE = '''"""Generated check: {ref}
Rendered by security_agents.checks.library from reviewed template parameters.
Runs the reviewed .sandbox/firestore_harness.mjs against the run's Firestore emulator,
which loads this workspace's own rules file. Only rules denials count as "denied".
"""

import json
import os
import pathlib
import subprocess
import tempfile

import pytest

PARAMS = {params}
RESULT = {{}}


@pytest.fixture(scope="module")
def outcomes():
    here, work = pathlib.Path(__file__).parent, pathlib.Path(tempfile.mkdtemp())
    params, out = work / "firestore_params.json", work / "firestore_out.json"
    params.write_text(json.dumps({{**PARAMS, "out": str(out)}}))
    subprocess.run(
        ["node", str(here / "firestore_harness.mjs"), str(params)],
        check=True, timeout=120, cwd=os.getcwd(),
    )
    rows = {{o["name"]: o for o in json.loads(out.read_text())["outcomes"]}}
    RESULT["outcomes"] = rows
    broken = [r for r in rows.values() if r["allowed"] is None]
    if broken:  # an error is not evidence either way: fail the fixture, not the assertion
        raise RuntimeError(f"emulator errors, no verdict: {{broken}}")
    if rows["owner_get"]["allowed"] is not True:
        # Positive control: if the owner cannot read either, the path is server-only or does
        # not fit this template. Inconclusive, never a finding.
        raise RuntimeError("positive control failed: the owner cannot read this document; no verdict")
    return rows
'''


def _firestore_path(recipe: dict[str, Any], path_id: str, uid: str) -> str:
    for fp in recipe.get("firestore_paths") or []:
        if isinstance(fp, dict) and fp.get("id") == path_id:
            filled = str(fp["path_template"]).replace("{uid}", uid)
            return _PATH_PARAM.sub("sbx-doc", filled)
    raise PlatformError(ErrorCode.SCHEMA_INVALID, f"unknown firestore path {path_id!r}")


def _firestore_identity(recipe: dict[str, Any], name: str) -> tuple[str, dict[str, Any]]:
    spec = (recipe.get("identities") or {}).get(name)
    if not isinstance(spec, dict) or not spec.get("uid"):
        raise PlatformError(ErrorCode.SCHEMA_INVALID, f"unknown fixture identity {name!r}")
    claims = dict(spec.get("claims") or {})
    if spec.get("email"):
        claims.update(email=spec["email"], email_verified=bool(spec.get("email_verified", False)))
    return str(spec["uid"]), claims


def _firestore_params(recipe: dict[str, Any], doc: str, ops: list[dict[str, Any]]) -> dict[str, Any]:
    firebase = recipe.get("firebase") or {}
    seeded = next(
        (s["data"] for s in recipe.get("seed") or [] if isinstance(s, dict) and s.get("path") == doc),
        {"sbx_seed": True},
    )
    return {
        "project_id": str(firebase.get("project_id", "demo-ari-sandbox")),
        "rules_path": str(firebase.get("rules", "firestore.rules")),
        "seed": [{"path": doc, "data": seeded}],
        "ops": ops,
    }


def _render_firestore_owner(recipe: dict[str, Any], params: dict[str, Any]) -> str:
    owner, other = str(params["owner_identity"]), str(params["other_identity"])
    if owner == other:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "owner_identity and other_identity must differ")
    owner_uid, owner_claims = _firestore_identity(recipe, owner)
    other_uid, other_claims = _firestore_identity(recipe, other)
    doc = _firestore_path(recipe, str(params["path_id"]), owner_uid)
    ops = [
        {"name": "owner_get", "op": "get", "path": doc, "as": owner_uid, "claims": owner_claims},
        {"name": "other_get", "op": "get", "path": doc, "as": other_uid, "claims": other_claims},
        {
            "name": "other_set",
            "op": "set",
            "path": doc,
            "as": other_uid,
            "claims": other_claims,
            "data": {"sbx_probe": True},
        },
    ]
    return (
        _FIRESTORE_PREAMBLE.format(ref=params["_ref"], params=repr(_firestore_params(recipe, doc, ops)))
        + """

def test_other_identity_is_denied(outcomes):
    leaked = [n for n in ("other_get", "other_set") if outcomes[n]["allowed"]]
    RESULT["other_leaked"] = leaked
    assert not leaked, f"rules allowed a different identity to {leaked} the owner's document"
"""
    )


def _render_firestore_unauthenticated(recipe: dict[str, Any], params: dict[str, Any]) -> str:
    owner_uid, owner_claims = _firestore_identity(recipe, str(params["owner_identity"]))
    doc = _firestore_path(recipe, str(params["path_id"]), owner_uid)
    ops = [
        {"name": "owner_get", "op": "get", "path": doc, "as": owner_uid, "claims": owner_claims},
        {"name": "anon_get", "op": "get", "path": doc, "as": None},
        {"name": "anon_list", "op": "list", "path": doc.rsplit("/", 1)[0], "as": None},
    ]
    return (
        _FIRESTORE_PREAMBLE.format(ref=params["_ref"], params=repr(_firestore_params(recipe, doc, ops)))
        + """

def test_unauthenticated_request_is_denied(outcomes):
    leaked = [n for n in ("anon_get", "anon_list") if outcomes[n]["allowed"]]
    RESULT["anon_leaked"] = leaked
    assert not leaked, f"rules allowed an unauthenticated client to {leaked}"
"""
    )


def _render_firestore_enumeration(recipe: dict[str, Any], params: dict[str, Any]) -> str:
    owner, other = str(params["owner_identity"]), str(params["other_identity"])
    if owner == other:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "owner_identity and other_identity must differ")
    owner_uid, owner_claims = _firestore_identity(recipe, owner)
    other_uid, other_claims = _firestore_identity(recipe, other)
    doc = _firestore_path(recipe, str(params["path_id"]), owner_uid)
    ops = [
        {"name": "owner_get", "op": "get", "path": doc, "as": owner_uid, "claims": owner_claims},
        {
            "name": "other_list",
            "op": "list",
            "path": doc.rsplit("/", 1)[0],
            "as": other_uid,
            "claims": other_claims,
        },
    ]
    return (
        _FIRESTORE_PREAMBLE.format(ref=params["_ref"], params=repr(_firestore_params(recipe, doc, ops)))
        + """

def test_collection_cannot_be_enumerated(outcomes):
    RESULT["other_listed"] = outcomes["other_list"]["allowed"]
    assert outcomes["other_list"]["allowed"] is False, "rules let another identity list the collection"
"""
    )


_FIRESTORE_PARAMS = ("path_id", "owner_identity", "other_identity")

FIRESTORE_OWNER = CheckTemplateMeta(
    template_id="firestore.owner_isolation",
    version="1",
    category="access_control.ownership",
    description=(
        "Firestore rules: the owner can read their document at a firestore_paths entry; a "
        "different fixture identity can neither read nor write it. Runs against the run's "
        "emulator with the workspace's rules. Parameters: path_id, owner_identity, other_identity."
    ),
    side_effect_class="ephemeral_target_only",
    expectation_kinds=("access_control", "authorization", "ownership"),
    parameters=_FIRESTORE_PARAMS,
    reviewed_by="security-owner:pending-human-signoff",
    support_files=("firestore_harness.mjs",),
)
FIRESTORE_UNAUTHENTICATED = CheckTemplateMeta(
    template_id="firestore.unauthenticated_denied",
    version="1",
    category="access_control.authentication",
    description=(
        "Firestore rules: an unauthenticated client can neither get a document at a "
        "firestore_paths entry nor list its collection; the owner keeps read access. "
        "Parameters: path_id, owner_identity."
    ),
    side_effect_class="ephemeral_target_only",
    expectation_kinds=("access_control", "authentication"),
    parameters=("path_id", "owner_identity"),
    reviewed_by="security-owner:pending-human-signoff",
    support_files=("firestore_harness.mjs",),
)
FIRESTORE_ENUMERATION = CheckTemplateMeta(
    template_id="firestore.collection_enumeration",
    version="1",
    category="access_control.ownership",
    description=(
        "Firestore rules: a different fixture identity cannot list the collection that holds "
        "the owner's document. Parameters: path_id, owner_identity, other_identity."
    ),
    side_effect_class="ephemeral_target_only",
    expectation_kinds=("access_control", "authorization", "ownership"),
    parameters=_FIRESTORE_PARAMS,
    reviewed_by="security-owner:pending-human-signoff",
    support_files=("firestore_harness.mjs",),
)


def _value_field(route: dict[str, Any]) -> tuple[str, str]:
    """(kind, field) of the value a create route moves: the source's remaining
    ``balance_field`` or its consumed ``accumulated_field``, read via the read route."""
    for kind in ("balance_field", "accumulated_field"):
        if route.get(kind):
            return kind, str(route[kind])
    raise PlatformError(
        ErrorCode.SCHEMA_INVALID, "create route declares neither balance_field nor accumulated_field"
    )


def _create_and_read(recipe: dict[str, Any], params: dict[str, Any]) -> tuple[dict, dict, str]:
    create = _route(recipe, str(params["route_id"]))
    read = _route(recipe, str(params["read_route_id"]))
    if str(create.get("method", "")).upper() != "POST":
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "template needs a POST create route")
    if not isinstance(create.get("body_template"), dict):
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "create route has no body_template")
    return create, read, str(params["owner_identity"])


def _body_src(body_template: dict[str, Any], values: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in body_template.items():
        out[key] = values.get(value, value) if isinstance(value, str) else value
    return out


def _render_concurrent_bound(recipe: dict[str, Any], params: dict[str, Any]) -> str:
    """The amount bound holds when the same create request arrives concurrently: no more
    value moves than the source holds, and the read-back value matches the accepted
    requests (no lost update). Covers check-then-act races (CWE-362/CWE-367)."""
    create, read, owner = _create_and_read(recipe, params)
    kind = str(create["resource"])
    resource_id = _resource_id(recipe, kind, owner)
    bound = Decimal(_resource_amount(recipe, kind, owner))
    field_kind, field_name = _value_field(create)
    try:
        parallel = int(params.get("parallel", 8))
    except (TypeError, ValueError) as exc:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "parallel must be an integer") from exc
    if not 2 <= parallel <= 16:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "parallel must be between 2 and 16")
    # Each request is 60% of the source: a serial implementation accepts exactly one.
    amount = (bound * Decimal("0.6")).quantize(Decimal("0.01"))
    if amount <= 0:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "resource amount is too small")
    values = {"{resource_id}": resource_id, "{amount}": str(amount)}
    if "{destination}" in create["body_template"].values():
        dest_kind = str(create.get("destination_resource") or kind)
        others = [o for o in sorted(recipe.get("resources", {}).get(dest_kind, {})) if o != owner]
        if not others:
            raise PlatformError(ErrorCode.SCHEMA_INVALID, f"no other identity owns a {dest_kind}")
        values["{destination}"] = _resource_id(recipe, dest_kind, others[0])
    body = _body_src(create["body_template"], values)
    read_path = _fill_path(str(read["path_template"]), resource_id)
    return (
        _inprocess_preamble(str(params["_ref"]), recipe)
        + f"""
import threading

import pytest
from concurrent.futures import ThreadPoolExecutor

CREATE_PATH = {str(create["path_template"])!r}
READ_PATH = {read_path!r}
HEADERS = {{"Authorization": {_identity(recipe, owner)!r}}}
BODY = {body!r}
BOUND = Decimal({str(bound)!r})
AMOUNT = Decimal({str(amount)!r})
PARALLEL = {parallel}
FIELD_KIND = {field_kind!r}
FIELD = {field_name!r}


def _read_value(client):
    resp = client.get(READ_PATH, headers=HEADERS)
    if resp.status_code != 200 or FIELD not in resp.json():
        # The owner cannot read its own resource: a setup problem, not evidence.
        pytest.skip(f"read-back failed: {{resp.status_code}}")
    return Decimal(str(resp.json()[FIELD]))


def test_bound_holds_under_concurrent_requests():
    client = _client()
    barrier = threading.Barrier(PARALLEL)

    def one(_):
        barrier.wait(timeout=30)
        return client.post(CREATE_PATH, json=BODY, headers=HEADERS).status_code

    with ThreadPoolExecutor(PARALLEL) as pool:
        statuses = list(pool.map(one, range(PARALLEL)))
    accepted = sum(1 for s in statuses if s < 400)
    value = _read_value(client)
    moved = accepted * AMOUNT
    expected = BOUND - moved if FIELD_KIND == "balance_field" else moved
    RESULT.update(statuses=statuses, accepted=accepted, moved=str(moved), value=str(value))
    if accepted == 0:
        # Not evidence either way: the request itself is rejected (wrong body, auth, amount).
        pytest.skip(f"no concurrent request was accepted: {{statuses}}")
    assert moved <= BOUND, (
        f"{{accepted}} concurrent requests of {{AMOUNT}} accepted against a bound of {{BOUND}}"
    )
    assert value == expected, (
        f"lost update: {{accepted}} accepted requests should leave {{FIELD}}={{expected}}, "
        f"observed {{value}}"
    )
"""
    )


CONCURRENT_BOUND = CheckTemplateMeta(
    template_id="input_validation.concurrent_bound",
    version="1",
    category="input_validation.bounds",
    description=(
        "Race-condition check (CWE-362): send the same create request (60% of the source "
        "amount each) `parallel` times at once (2-16, default 8). Fails if more value moves "
        "than the source holds or the read-back value disagrees with the accepted requests "
        "(lost update). Needs a POST create route with body_template and balance_field or "
        "accumulated_field. Parameters: route_id, read_route_id, owner_identity, parallel."
    ),
    side_effect_class="ephemeral_target_only",
    expectation_kinds=("business_rule", "invariant", "input_validation", "concurrency"),
    parameters=("route_id", "read_route_id", "owner_identity", "parallel"),
    reviewed_by="security-owner:pending-human-signoff",
)

NONEXISTENT_DESTINATION = "ari-probe-nonexistent-destination"


def _render_destination(recipe: dict[str, Any], params: dict[str, Any]) -> str:
    """A create request naming an invalid destination is rejected and moves no value.
    The destination is either an id that does not exist or, when the API requires the
    caller to own the destination, another fixture identity's resource."""
    create, read, owner = _create_and_read(recipe, params)
    if "{destination}" not in create["body_template"].values():
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "create route body_template has no {destination}")
    kind = str(create["resource"])
    resource_id = _resource_id(recipe, kind, owner)
    bound = Decimal(_resource_amount(recipe, kind, owner))
    _, field_name = _value_field(create)
    other = params.get("destination_identity")
    if other is None:
        destination = NONEXISTENT_DESTINATION
    else:
        if str(other) == owner:
            raise PlatformError(ErrorCode.SCHEMA_INVALID, "destination_identity must differ from owner")
        destination = _resource_id(recipe, str(create.get("destination_resource") or kind), str(other))
    amount = min(Decimal("1.00"), bound)
    body = _body_src(
        create["body_template"],
        {"{resource_id}": resource_id, "{amount}": str(amount), "{destination}": destination},
    )
    read_path = _fill_path(str(read["path_template"]), resource_id)
    return (
        _inprocess_preamble(str(params["_ref"]), recipe)
        + f"""
import pytest

CREATE_PATH = {str(create["path_template"])!r}
READ_PATH = {read_path!r}
HEADERS = {{"Authorization": {_identity(recipe, owner)!r}}}
BODY = {body!r}
FIELD = {field_name!r}


def _read_value(client):
    resp = client.get(READ_PATH, headers=HEADERS)
    if resp.status_code != 200 or FIELD not in resp.json():
        # The owner cannot read its own resource: a setup problem, not evidence.
        pytest.skip(f"read-back failed: {{resp.status_code}}")
    return Decimal(str(resp.json()[FIELD]))


def test_invalid_destination_is_rejected_and_moves_nothing():
    client = _client()
    before = _read_value(client)
    resp = client.post(CREATE_PATH, json=BODY, headers=HEADERS)
    after = _read_value(client)
    RESULT.update(status=resp.status_code, before=str(before), after=str(after))
    assert after == before, f"{{FIELD}} changed from {{before}} to {{after}} for an invalid destination"
    assert 400 <= resp.status_code < 500, (
        f"expected 4xx for an invalid destination, observed {{resp.status_code}}"
    )
"""
    )


DESTINATION = CheckTemplateMeta(
    template_id="input_validation.destination",
    version="1",
    category="input_validation.bounds",
    description=(
        "Destination-reference check (CWE-1284/CWE-639): a create request whose {destination} "
        "does not exist (default) or, with destination_identity, belongs to another fixture "
        "identity, must be rejected 4xx and leave the source value unchanged. Use "
        "destination_identity only when the API requires the caller to own the destination. "
        "Parameters: route_id, read_route_id, owner_identity, destination_identity."
    ),
    side_effect_class="ephemeral_target_only",
    expectation_kinds=("business_rule", "invariant", "input_validation", "access_control"),
    parameters=("route_id", "read_route_id", "owner_identity", "destination_identity"),
    reviewed_by="security-owner:pending-human-signoff",
)


_SQLI_PAYLOADS = ("' OR '1'='1' --", "' OR 1=1 --", '" OR "1"="1" --')


def _render_sql_injection(recipe: dict[str, Any], params: dict[str, Any]) -> str:
    """A search/filter route must parameterise its query: an injection payload sent by
    one identity cannot widen the query to return a row owned only by another identity
    (CWE-89). The owner sends classic tautology payloads; the other identity's resource
    id is the canary that must never appear in the response."""
    route = _route(recipe, str(params["route_id"]))
    if str(route.get("method", "GET")).upper() != "GET":
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "sql_injection template covers GET search routes only")
    owner, other = str(params["owner_identity"]), str(params["other_identity"])
    if owner == other:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "owner_identity and other_identity must differ")
    path = str(route["path_template"])
    if _PATH_PARAM.findall(path):
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "search route must not take a path parameter")
    query_param = str(route.get("query_param") or "q")
    canary = _resource_id(recipe, str(route["resource"]), other)
    return (
        _inprocess_preamble(str(params["_ref"]), recipe)
        + f"""
import pytest

PATH = {path!r}
QUERY_PARAM = {query_param!r}
HEADERS = {{"Authorization": {_identity(recipe, owner)!r}}}
CANARY = {canary!r}
PAYLOADS = {list(_SQLI_PAYLOADS)!r}


def test_injection_cannot_leak_another_identitys_rows():
    client = _client()
    # Baseline: a benign owner query must not already surface the other identity's row;
    # if it does, that is a data-isolation problem for another check, not a SQLi signal.
    benign = client.get(PATH, params={{QUERY_PARAM: "ari-probe-no-such-term"}}, headers=HEADERS)
    if benign.status_code != 200:
        pytest.skip(f"search route did not answer a benign query: {{benign.status_code}}")
    if CANARY in benign.text:
        pytest.skip("another identity's row is visible without injection; not a SQLi signal")
    for payload in PAYLOADS:
        resp = client.get(PATH, params={{QUERY_PARAM: payload}}, headers=HEADERS)
        RESULT.setdefault("statuses", []).append(resp.status_code)
        assert CANARY not in resp.text, (
            f"injection payload {{payload!r}} leaked another identity's row ({{CANARY}})"
        )
"""
    )


SQL_INJECTION = CheckTemplateMeta(
    template_id="input_validation.sql_injection",
    version="1",
    category="input_validation.injection",
    description=(
        "SQL-injection check (CWE-89): a GET search/filter route must parameterise its query. "
        "The owner sends classic tautology payloads (' OR '1'='1' --); none may return a row "
        "owned only by another fixture identity. Skips when the benign query already surfaces "
        "that row (a data-isolation problem for another check). Needs a GET route with a "
        "resource kind and an optional query_param (default q). Parameters: route_id, "
        "owner_identity, other_identity."
    ),
    side_effect_class="read_only",
    expectation_kinds=("input_validation", "injection"),
    parameters=("route_id", "owner_identity", "other_identity"),
    reviewed_by="security-owner:pending-human-signoff",
)


_RENDERERS = {
    OWNERSHIP.ref: _render_ownership,
    BOUNDS.ref: _render_bounds,
    AUTHENTICATION.ref: _render_authentication,
    ROLE.ref: _render_role,
    FIRESTORE_OWNER.ref: _render_firestore_owner,
    FIRESTORE_UNAUTHENTICATED.ref: _render_firestore_unauthenticated,
    FIRESTORE_ENUMERATION.ref: _render_firestore_enumeration,
    CONCURRENT_BOUND.ref: _render_concurrent_bound,
    DESTINATION.ref: _render_destination,
    SQL_INJECTION.ref: _render_sql_injection,
}


@dataclass
class CheckLibrary:
    templates: dict[str, CheckTemplateMeta] = field(default_factory=dict)

    def register(self, meta: CheckTemplateMeta) -> None:
        self.templates[meta.ref] = meta

    def list_public(self) -> list[dict[str, Any]]:
        return [m.public() for m in self.templates.values()]

    def categories(self) -> set[str]:
        return {m.category for m in self.templates.values()}

    def get(self, ref: str) -> CheckTemplateMeta | None:
        return self.templates.get(ref)

    def runnable(self, ref: str) -> bool:
        meta = self.get(ref)
        return meta is not None and meta.reviewed_by is not None and ref in _RENDERERS

    def render(
        self, ref: str, recipe: dict[str, Any], params: dict[str, Any], transport: str = "inprocess"
    ) -> str:
        if transport not in TRANSPORTS:
            raise PlatformError(ErrorCode.SCHEMA_INVALID, f"unknown check transport {transport!r}")
        meta = self.get(ref)
        if meta is None:
            raise PlatformError(ErrorCode.SCHEMA_INVALID, f"unknown check template {ref!r}")
        if not self.runnable(ref):
            raise PlatformError(
                ErrorCode.SANDBOX_POLICY_VIOLATION,
                f"template {ref} has no reviewed implementation installed",
            )
        unknown = set(params) - set(meta.parameters)
        if unknown:
            raise PlatformError(ErrorCode.SCHEMA_INVALID, f"unknown parameters {sorted(unknown)}")
        optional = {"over_by", "expected_denied_status", "parallel", "destination_identity"}
        missing = [p for p in meta.parameters if p not in params and p not in optional]
        if missing:
            raise PlatformError(ErrorCode.SCHEMA_INVALID, f"missing parameters {missing}")
        if meta.support_files:  # self-contained harness checks: no HTTP target involved
            transport = "inprocess"
        if transport == "http" and meta.side_effect_class != "read_only":
            raise PlatformError(
                ErrorCode.SANDBOX_POLICY_VIOLATION,
                f"{ref} changes target state; the http transport supports read_only templates only",
            )
        enriched = dict(params)
        enriched["_ref"] = ref
        rendered = _RENDERERS[ref](recipe, enriched)
        if transport == "http" and not meta.support_files:
            inprocess = _inprocess_preamble(ref, recipe)
            if not rendered.startswith(inprocess):
                raise PlatformError(ErrorCode.SANDBOX_POLICY_VIOLATION, f"{ref} cannot be rendered for http")
            rendered = _PREAMBLE_HTTP.format(ref=ref) + rendered[len(inprocess) :]
        return rendered

    def applicable(self, ref: str, recipe: dict[str, Any]) -> bool:
        """Harness (Firestore) templates need firestore_paths; HTTP templates need routes."""
        meta = self.get(ref)
        if meta is None:
            return False
        return bool(recipe.get("firestore_paths" if meta.support_files else "routes"))

    def parameter_values(self, ref: str, recipe: dict[str, Any]) -> dict[str, Any]:
        meta = self.get(ref)
        if meta is None:
            return {}
        routes = [r for r in recipe.get("routes", []) if isinstance(r, dict) and r.get("id")]

        def describe(route: dict[str, Any]) -> dict[str, Any]:
            return {
                "id": route["id"],
                "method": str(route.get("method", "GET")).upper(),
                "path_template": route.get("path_template"),
                "resource": route.get("resource"),
            }

        def single_param_get(route: dict[str, Any]) -> bool:
            return str(route.get("method", "GET")).upper() == "GET" and (
                len(_PATH_PARAM.findall(str(route.get("path_template", "")))) == 1
            )

        identities = sorted(recipe.get("identities", {}))
        values: dict[str, Any] = {}
        for name in meta.parameters:
            if name in ("owner_identity", "other_identity", "identity") or name in (
                "restricted_identity",
                "permitted_identity",
            ):
                values[name] = identities
            elif name == "route_id" and meta.template_id == ROLE.template_id:
                values[name] = [
                    describe(r)
                    for r in routes
                    if str(r.get("method", "GET")).upper() in _MUTATING
                    and len(_PATH_PARAM.findall(str(r.get("path_template", "")))) <= 1
                ]
            elif name == "route_id" and meta.template_id == AUTHENTICATION.template_id:
                values[name] = [
                    describe(r)
                    for r in routes
                    if str(r.get("method", "GET")).upper() == "GET"
                    and len(_PATH_PARAM.findall(str(r.get("path_template", "")))) <= 1
                ]
            elif name == "read_route_id" or (
                name == "route_id" and meta.template_id == OWNERSHIP.template_id
            ):
                values[name] = [describe(r) for r in routes if single_param_get(r)]
            elif name == "route_id":
                values[name] = [
                    describe(r)
                    for r in routes
                    if str(r.get("method", "")).upper() == "POST" and isinstance(r.get("body_template"), dict)
                ]
            elif name == "path_id":
                values[name] = [
                    {"id": fp.get("id"), "path_template": fp.get("path_template")}
                    for fp in recipe.get("firestore_paths") or []
                    if isinstance(fp, dict)
                ]
            elif name == "destination_identity":
                values[name] = ["omit for a nonexistent destination", *identities]
            elif name == "parallel":
                values[name] = "optional integer 2-16, default 8"
            elif name == "over_by":
                values[name] = "optional positive decimal string, default 1.00"
        return values

    def params_hash(self, ref: str, params: dict[str, Any]) -> str:
        import hashlib

        payload = json.dumps({"ref": ref, "params": params}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def default_library() -> CheckLibrary:
    lib = CheckLibrary()
    lib.register(OWNERSHIP)
    lib.register(BOUNDS)
    lib.register(AUTHENTICATION)
    lib.register(ROLE)
    lib.register(FIRESTORE_OWNER)
    lib.register(FIRESTORE_UNAUTHENTICATED)
    lib.register(FIRESTORE_ENUMERATION)
    lib.register(CONCURRENT_BOUND)
    lib.register(DESTINATION)
    lib.register(SQL_INJECTION)
    return lib


def empty_library() -> CheckLibrary:
    """Library with no reviewed implementations: every run fails closed."""
    return CheckLibrary()
