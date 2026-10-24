"""The security agents' sandbox target: the real app, seeded fixture users, bearer mapping."""

import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]


def _target():
    spec = importlib.util.spec_from_file_location(
        "sandbox_target", ROOT / "deploy" / "sandbox_target.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fill_body(value: Any, recipe: dict[str, Any], owner: str) -> Any:
    if isinstance(value, str) and value.startswith("{resource:") and value.endswith("}"):
        kind = value[len("{resource:") : -1]
        return recipe["resources"][kind][owner]["id"]
    if isinstance(value, str) and value.startswith("{expires_in_days:") and value.endswith("}"):
        days = int(value[len("{expires_in_days:") : -1])
        return (datetime.now(tz=UTC) + timedelta(days=days)).isoformat()
    if isinstance(value, dict):
        return {key: _fill_body(item, recipe, owner) for key, item in value.items()}
    if isinstance(value, list):
        return [_fill_body(item, recipe, owner) for item in value]
    return value


def test_every_recipe_route_allows_the_owner_and_denies_the_other_user(monkeypatch):
    monkeypatch.setenv("SANDBOX_TARGET_DATABASE_URL", os.environ["DATABASE_URL"])
    recipe = json.loads((ROOT / "build_recipe.json").read_text())
    client = TestClient(_target().create_app())
    ident = {k: {"Authorization": v["auth_header"]} for k, v in recipe["identities"].items()}
    for route in recipe["routes"]:
        rid = recipe["resources"][route["resource"]]["alice"]["id"]
        path = route["path_template"].split("{")[0] + rid + route["path_template"].split("}")[1]
        method = str(route.get("method") or "GET").upper()
        payload = route.get("body_template")
        body = _fill_body(payload, recipe, "alice") if payload is not None else None
        kwargs: dict[str, Any] = {}
        if body is not None:
            kwargs["json"] = body
        owner = client.request(method, path, headers=ident["alice"], **kwargs)
        assert owner.status_code in (200, 201), (route["id"], owner.status_code, owner.text[:300])
        other = client.request(method, path, headers=ident["bob"], **kwargs)
        assert other.status_code in (403, 404), (route["id"], other.status_code)
        anon = client.request(method, path, **kwargs)
        assert anon.status_code == 401, (route["id"], anon.status_code)
