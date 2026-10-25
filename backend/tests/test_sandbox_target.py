"""The security agents' sandbox target: the real app, seeded fixture users, bearer mapping."""

import importlib.util
import json
import os
import re
from datetime import UTC
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]


def _target():
    spec = importlib.util.spec_from_file_location(
        "sandbox_target", ROOT / "deploy" / "sandbox_target.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _render(value: object, recipe: dict, owner: str, route_kind: str) -> object:
    """Substitute the build recipe's body_template placeholders for `owner`.

    Mirrors the check library's render rules: `{resource:<kind>}` and `{resource_id}`
    become the owner's resource id of that kind, `{expires_in_days:N}` an ISO timestamp
    N days out, everything else passes through.
    """
    if isinstance(value, dict):
        return {k: _render(v, recipe, owner, route_kind) for k, v in value.items()}
    if isinstance(value, list):
        return [_render(v, recipe, owner, route_kind) for v in value]
    if isinstance(value, str):
        m = re.fullmatch(r"\{expires_in_days:(\d{1,3})\}", value)
        if m:
            from datetime import datetime, timedelta

            return (datetime.now(UTC) + timedelta(days=int(m.group(1)))).isoformat()
        m = re.fullmatch(r"\{resource:([A-Za-z_][A-Za-z0-9_]*)\}", value)
        if m:
            return recipe["resources"][m.group(1)][owner]["id"]
        if value == "{resource_id}":
            return recipe["resources"][route_kind][owner]["id"]
    return value


def test_every_recipe_route_allows_the_owner_and_denies_the_other_user(monkeypatch):
    monkeypatch.setenv("SANDBOX_TARGET_DATABASE_URL", os.environ["DATABASE_URL"])
    recipe = json.loads((ROOT / "build_recipe.json").read_text())
    client = TestClient(_target().create_app())
    ident = {k: {"Authorization": v["auth_header"]} for k, v in recipe["identities"].items()}
    for route in recipe["routes"]:
        rid = recipe["resources"][route["resource"]]["alice"]["id"]
        path = route["path_template"].split("{")[0] + rid + route["path_template"].split("}")[1]
        kwargs = (
            {"json": _render(route["body_template"], recipe, "alice", route["resource"])}
            if "body_template" in route
            else {}
        )
        call = client.post if route.get("method", "GET").upper() == "POST" else client.get
        assert 200 <= call(path, headers=ident["alice"], **kwargs).status_code < 300, route["id"]
        assert call(path, headers=ident["bob"], **kwargs).status_code in (403, 404), route["id"]
        assert call(path, **kwargs).status_code == 401, route["id"]
