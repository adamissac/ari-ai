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
        "1ae4952e7c12dff049d9939e9a976fd0d57f1f0f",
        "backend/backend/migrations/versions/0018_execution_reliability.py",
        "revision",
    )
    disconnect = _literal(
        "da14512608626512415ba2aafdf207c1b1a16747",
        "backend/backend/migrations/versions/0019_repository_disconnect.py",
        "revision",
    )
    assert reliability != disconnect, "both transfer branches still declare revision " + reliability


def test_declared_transfer_order_does_not_downgrade_schema():
    heads = [
        "40f1e333fbaf5ee2a00117e26d3b19d4b0e4f7ee",
        "286f20af7197db9fa230438419bb3e3fca43aee5",
        "da14512608626512415ba2aafdf207c1b1a16747",
        "36ebc704fcc2a5dc0a4f4f77b7c0f352aca6cb15",
    ]
    versions = [_literal(sha, "shared/shared/__init__.py", "SCHEMA_VERSION") for sha in heads]
    assert all(isinstance(v, str) for v in versions), versions
    numeric = [tuple(map(int, v.split("."))) for v in versions]
    assert numeric == sorted(numeric), versions
