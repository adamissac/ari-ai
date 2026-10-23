"""The security agents' sandbox target: the real app, seeded fixture users, bearer mapping."""

import importlib.util
import json
import os
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


def test_every_recipe_route_allows_the_owner_and_denies_the_other_user(monkeypatch):
    monkeypatch.setenv("SANDBOX_TARGET_DATABASE_URL", os.environ["DATABASE_URL"])
    recipe = json.loads((ROOT / "build_recipe.json").read_text())
    client = TestClient(_target().create_app())
    ident = {k: {"Authorization": v["auth_header"]} for k, v in recipe["identities"].items()}
    for route in recipe["routes"]:
        rid = recipe["resources"][route["resource"]]["alice"]["id"]
        path = route["path_template"].split("{")[0] + rid + route["path_template"].split("}")[1]
        assert client.get(path, headers=ident["alice"]).status_code == 200, route["id"]
        assert client.get(path, headers=ident["bob"]).status_code in (403, 404), route["id"]
        assert client.get(path).status_code == 401, route["id"]
