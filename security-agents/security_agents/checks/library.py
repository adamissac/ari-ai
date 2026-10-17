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
        optional = {"over_by", "expected_denied_status"}
        missing = [p for p in meta.parameters if p not in params and p not in optional]
        if missing:
            raise PlatformError(ErrorCode.SCHEMA_INVALID, f"missing parameters {missing}")
        if transport == "http" and meta.side_effect_class != "read_only":
            raise PlatformError(
                ErrorCode.SANDBOX_POLICY_VIOLATION,
                f"{ref} changes target state; the http transport supports read_only templates only",
            )
        enriched = dict(params)
        enriched["_ref"] = ref
        rendered = _RENDERERS[ref](recipe, enriched)
        if transport == "http":
            inprocess = _inprocess_preamble(ref, recipe)
            if not rendered.startswith(inprocess):
                raise PlatformError(ErrorCode.SANDBOX_POLICY_VIOLATION, f"{ref} cannot be rendered for http")
            rendered = _PREAMBLE_HTTP.format(ref=ref) + rendered[len(inprocess) :]
        return rendered

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
            if name in ("owner_identity", "other_identity"):
                values[name] = identities
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
    return lib


def empty_library() -> CheckLibrary:
    """Library with no reviewed implementations: every run fails closed."""
    return CheckLibrary()
