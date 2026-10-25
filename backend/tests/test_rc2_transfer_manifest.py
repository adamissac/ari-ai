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
        "0f54d8bc940f96f8346bdf88e03a1a099d435fd4",
        "backend/backend/migrations/versions/0018_execution_reliability.py",
        "revision",
    )
    disconnect = _literal(
        "f4237cec046631e97db60fc5cffb12e49c5c0855",
        "backend/backend/migrations/versions/0019_repository_disconnect.py",
        "revision",
    )
    assert reliability != disconnect, "both transfer branches still declare revision " + reliability


def test_declared_transfer_order_does_not_downgrade_schema():
    heads = [
        "93b4fe82b8f12df50486b2f452d9d0d339e93bee",
        "d23d72a826688cc0fcd2d4035465585be15be2e0",
        "f4237cec046631e97db60fc5cffb12e49c5c0855",
        "a6e163323e01a38e4a901a39525cf222278c54b2",
    ]
    versions = [_literal(sha, "shared/shared/__init__.py", "SCHEMA_VERSION") for sha in heads]
    assert all(isinstance(v, str) for v in versions), versions
    numeric = [tuple(map(int, v.split("."))) for v in versions]
    assert numeric == sorted(numeric), versions
