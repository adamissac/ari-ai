"""Keep build_recipe.json (operator config, owner: Alan) consistent with the real target.

Skipped until build_recipe.json exists on the branch. Checks that every identity, seeded
resource and route the recipe names really exists in target/, so Probe/Verify can never be
pointed at ids or routes the app does not have.
"""

import ast
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
RECIPE_PATH = ROOT / "build_recipe.json"
if not RECIPE_PATH.exists():
    pytest.skip("build_recipe.json not present", allow_module_level=True)
sys.path.insert(0, str(ROOT / "target"))
from payments_lite.app import create_app  # noqa: E402

RECIPE = json.loads(RECIPE_PATH.read_text())


def app_routes() -> set[tuple[str, str]]:
    src = (ROOT / "target/payments_lite/app.py").read_text()
    out = set()
    for node in ast.walk(ast.parse(src)):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "attr", "") in {"get", "post", "put", "patch", "delete"}
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            out.add((node.func.attr.upper(), node.args[0].value))
    return out


def _shape(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def test_recipe_points_at_target_dir_and_factory():
    assert RECIPE["target_dir"] == "target"
    module, _, attr = RECIPE["app_factory"].partition(":")
    assert module == "payments_lite.app" and attr == "create_app"


def test_every_recipe_route_exists_in_the_app():
    real = {(m, _shape(p)) for m, p in app_routes()}
    for r in RECIPE["routes"]:
        assert (r["method"], _shape(r["path_template"])) in real, r["id"]


def test_recipe_identities_and_resources_match_seeded_data():
    client = TestClient(create_app())
    for name, ident in RECIPE["identities"].items():
        me = client.get("/me", headers={"Authorization": ident["auth_header"]})
        assert me.status_code == 200 and me.json()["id"] == ident["customer_id"], name
    for owner, res in RECIPE["resources"]["payment"].items():
        headers = {"Authorization": RECIPE["identities"][owner]["auth_header"]}
        p = client.get(f"/payments/{res['id']}", headers=headers).json()
        assert Decimal(p[res["amount_field"]]) == Decimal(res["amount"]), owner
        assert res["refunded_field"] in p


def test_recipe_is_not_an_answer_key():
    text = RECIPE_PATH.read_text().lower()
    for leak in ("planted", "fnd_", "cwe-", "vulnerab", "missing ownership"):
        assert leak not in text, leak
