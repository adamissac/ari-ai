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
from dataclasses import dataclass, field
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
    raise PlatformError(ErrorCode.SCHEMA_INVALID, f"route_id {route_id!r} is not in the build recipe")


def _identity(recipe: dict[str, Any], name: str) -> str:
    ident = recipe.get("identities", {}).get(name)
    if not ident or "auth_header" not in ident:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, f"identity {name!r} is not in the build recipe")
    return str(ident["auth_header"])


def _resource_id(recipe: dict[str, Any], kind: str, owner: str) -> str:
    entry = recipe.get("resources", {}).get(kind, {}).get(owner)
    if not entry or "id" not in entry:
        raise PlatformError(
            ErrorCode.SCHEMA_INVALID, f"resource {kind!r} for identity {owner!r} is not in the build recipe"
        )
    return str(entry["id"])


def _resource_amount(recipe: dict[str, Any], kind: str, owner: str) -> int:
    entry = recipe.get("resources", {}).get(kind, {}).get(owner, {})
    amount = entry.get("amount_cents")
    if not isinstance(amount, int):
        raise PlatformError(ErrorCode.SCHEMA_INVALID, f"resource {kind}/{owner} has no amount_cents")
    return amount


_PREAMBLE = '''"""Generated check: {ref}
Rendered by security_agents.checks.library from reviewed template parameters.
Target is driven in-process through its own app factory; no sockets are opened.
"""

import json

from fastapi.testclient import TestClient

from payments_lite.app import create_app

RESULT = {{}}


def _client():
    return TestClient(create_app())
'''


# --------------------------------------------------------------------------- templates


def _render_ownership(recipe: dict[str, Any], params: dict[str, Any]) -> str:
    """Owner keeps access; a different fixture identity is denied the same resource."""
    route = _route(recipe, str(params["route_id"]))
    kind = str(route["resource"])
    owner, other = str(params["owner_identity"]), str(params["other_identity"])
    if owner == other:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "owner_identity and other_identity must differ")
    path = str(route["path_template"]).replace("{id}", _resource_id(recipe, kind, owner))
    method = str(route.get("method", "GET")).lower()
    if method != "get":
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "ownership template covers read routes only")
    denied = [int(c) for c in params.get("expected_denied_status", [403, 404])]
    return _PREAMBLE.format(ref=params["_ref"]) + f'''

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
'''


def _render_bounds(recipe: dict[str, Any], params: dict[str, Any]) -> str:
    """A request exceeding the documented amount bound must be rejected 4xx."""
    route = _route(recipe, str(params["route_id"]))
    kind = str(route["resource"])
    owner = str(params["owner_identity"])
    amount_field = str(route.get("amount_field") or "")
    if str(route.get("method", "")).upper() != "POST" or not amount_field:
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "bounds template needs a POST route with amount_field")
    resource_id = _resource_id(recipe, kind, owner)
    base = _resource_amount(recipe, kind, owner)
    over = base + int(params.get("over_by_cents", 1))
    read_route = _route(recipe, str(params["read_route_id"]))
    read_path = str(read_route["path_template"]).replace("{id}", resource_id)
    return _PREAMBLE.format(ref=params["_ref"]) + f'''

PATH = {str(route["path_template"]).replace("{id}", resource_id)!r}
READ_PATH = {read_path!r}
HEADERS = {{"Authorization": {_identity(recipe, owner)!r}}}
AMOUNT_FIELD = {amount_field!r}
BASE_AMOUNT = {base}
OVER_AMOUNT = {over}


def test_in_bounds_request_is_accepted():
    resp = _client().post(PATH, json={{AMOUNT_FIELD: 1}}, headers=HEADERS)
    RESULT["in_bounds_status"] = resp.status_code
    assert resp.status_code < 400, f"legitimate in-bounds request rejected: {{resp.status_code}}"


def test_over_bound_request_is_rejected():
    client = _client()
    resp = client.post(PATH, json={{AMOUNT_FIELD: OVER_AMOUNT}}, headers=HEADERS)
    RESULT["over_bound_status"] = resp.status_code
    total = sum(item[AMOUNT_FIELD] for item in client.get(READ_PATH, headers=HEADERS).json())
    RESULT["accumulated_total"] = total
    RESULT["bound"] = BASE_AMOUNT
    assert 400 <= resp.status_code < 500, (
        f"expected 4xx for an amount above the {{BASE_AMOUNT}} bound, observed {{resp.status_code}}"
    )
    assert total <= BASE_AMOUNT, f"invariant broken: accumulated {{total}} exceeds bound {{BASE_AMOUNT}}"
'''


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
        "Confirm a documented amount bound is enforced: an in-bounds request succeeds, a request "
        "above the bound is rejected 4xx and the accumulated total stays within the bound. "
        "Parameters: route_id, read_route_id, owner_identity, over_by_cents."
    ),
    side_effect_class="ephemeral_target_only",
    expectation_kinds=("business_rule", "input_validation"),
    parameters=("route_id", "read_route_id", "owner_identity", "over_by_cents"),
    reviewed_by="security-owner:pending-human-signoff",
)

_RENDERERS = {OWNERSHIP.ref: _render_ownership, BOUNDS.ref: _render_bounds}


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

    def render(self, ref: str, recipe: dict[str, Any], params: dict[str, Any]) -> str:
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
        missing = [p for p in meta.parameters if p not in params and p != "over_by_cents"]
        if missing:
            raise PlatformError(ErrorCode.SCHEMA_INVALID, f"missing parameters {missing}")
        enriched = dict(params)
        enriched["_ref"] = ref
        return _RENDERERS[ref](recipe, enriched)

    def params_hash(self, ref: str, params: dict[str, Any]) -> str:
        import hashlib

        payload = json.dumps({"ref": ref, "params": params}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def default_library() -> CheckLibrary:
    lib = CheckLibrary()
    lib.register(OWNERSHIP)
    lib.register(BOUNDS)
    return lib


def empty_library() -> CheckLibrary:
    """Library with no reviewed implementations: every run fails closed."""
    return CheckLibrary()
