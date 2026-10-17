from __future__ import annotations

from backend.integrations import load_factory


def _boom() -> object:
    raise RuntimeError("missing INTELLIGENCE_DB_PATH")


def test_missing_module_and_failing_factory_are_reported_not_raised() -> None:
    missing = load_factory("no_such_pkg_xyz.api:build")
    assert missing.obj is None and "not installed" in (missing.reason or "")
    failing = load_factory("test_integrations_loader:_boom")
    assert failing.obj is None and "missing INTELLIGENCE_DB_PATH" in (failing.reason or "")
    assert load_factory("test_integrations_loader:nope").reason
    assert load_factory("badspec").reason == "invalid factory spec 'badspec'"
