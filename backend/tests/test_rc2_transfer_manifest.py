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
        "5e130915d30aad375adc9750f2232e2d29c085cb",
        "backend/backend/migrations/versions/0018_execution_reliability.py",
        "revision",
    )
    disconnect = _literal(
        "89a29d170d4cf1f589975713ee7c8ada778f1ab6",
        "backend/backend/migrations/versions/0019_repository_disconnect.py",
        "revision",
    )
    assert reliability != disconnect, "both transfer branches still declare revision " + reliability


def test_declared_transfer_order_does_not_downgrade_schema():
    heads = [
        "93b4fe82b8f12df50486b2f452d9d0d339e93bee",
        "660a3575d9eaf0a2df67a50002b2ec924f182f23",
        "89a29d170d4cf1f589975713ee7c8ada778f1ab6",
        "10e923d1ffda75b19b848a7154f8ba867a0a8589",
    ]
    versions = [_literal(sha, "shared/shared/__init__.py", "SCHEMA_VERSION") for sha in heads]
    assert all(isinstance(v, str) for v in versions), versions
    numeric = [tuple(map(int, v.split("."))) for v in versions]
    assert numeric == sorted(numeric), versions
