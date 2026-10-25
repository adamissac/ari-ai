"""Read-only checks of exact upstream-targeted transfer Git objects."""

import ast
import subprocess


def _literal(sha, path, variable):
    source = subprocess.check_output(["git", "show", sha + ":" + path], text=True)
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == variable for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(variable)


def test_proposed_transfer_migrations_do_not_reuse_revision_ids():
    reliability = _literal(
        "b8ccb7a8305aa3e23212858c2f858c842b3939f0",
        "backend/backend/migrations/versions/0018_execution_reliability.py",
        "revision",
    )
    disconnect = _literal(
        "87fd714997b30145b08f34958e1bdc2d3b73eb18",
        "backend/backend/migrations/versions/0019_repository_disconnect.py",
        "revision",
    )
    assert reliability != disconnect, "both transfer branches still declare revision " + reliability


def test_declared_transfer_order_does_not_downgrade_schema():
    heads = [
        "93b4fe82b8f12df50486b2f452d9d0d339e93bee",
        "19b97702ab2a917a02a3e183bf7eda98eafbc8cd",
        "87fd714997b30145b08f34958e1bdc2d3b73eb18",
        "e6b7a3267b01dfbd30792600520cf34b9eccac59",
    ]
    versions = [_literal(sha, "shared/shared/__init__.py", "SCHEMA_VERSION") for sha in heads]
    assert all(isinstance(v, str) for v in versions), versions
    numeric = [tuple(map(int, v.split("."))) for v in versions]
    assert numeric == sorted(numeric), versions
