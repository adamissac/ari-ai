"""Keep build_recipe.json (operator config) consistent with the real target.

Run from examples/helpdesk-lite:
    target/.venv/bin/python -m pytest -q label_checks
"""

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
RECIPE_PATH = ROOT / "build_recipe.json"
sys.path.insert(0, str(ROOT / "target"))
from helpdesk_lite.app import create_app  # noqa: E402

RECIPE = json.loads(RECIPE_PATH.read_text())


def test_every_recipe_route_exists_in_the_app():
    paths = create_app().openapi()["paths"]
    real = {(method.upper(), path) for path, ops in paths.items() for method in ops}
    for route in RECIPE["routes"]:
        assert (route["method"], route["path_template"]) in real, route["id"]


def test_recipe_identities_and_resources_match_seeded_data():
    client = TestClient(create_app())
    for name, ident in RECIPE["identities"].items():
        headers = {"Authorization": ident["auth_header"]}
        assert client.get("/me", headers=headers).json()["id"] == ident["agent_id"], name
        for kind, path in (
            ("ticket", "tickets"),
            ("customer", "customers"),
            ("attachment", "attachments"),
        ):
            rid = RECIPE["resources"][kind][name]["id"]
            assert client.get(f"/{path}/{rid}", headers=headers).status_code == 200, rid


def test_sample_files_are_served():
    client = TestClient(create_app())
    headers = {"Authorization": RECIPE["identities"]["alice"]["auth_header"]}
    for route in RECIPE["routes"]:
        if route.get("sample_file"):
            r = client.get(
                route["path_template"], params={"file": route["sample_file"]}, headers=headers
            )
            assert r.status_code == 200, route["id"]


def test_recipe_is_not_an_answer_key():
    text = RECIPE_PATH.read_text().lower()
    for leak in ("planted", "fnd_", "cwe-", "vulnerab", "missing"):
        assert leak not in text, leak
