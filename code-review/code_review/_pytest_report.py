"""Pytest plugin copied into the sandbox: records each test's outcome and exception type.

Loaded with ``-p cr_pytest_report``; writes JSON to ``$CR_REPORT_PATH``. It lets the
reviewer tell a behavioral failure (AssertionError / pytest.fail) from a tooling error
(ImportError, NameError, collection error) without trusting model claims.
"""

import json
import os

import pytest

_RESULTS = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" or report.failed or (report.skipped and report.when == "setup"):
        exc_type = call.excinfo.type.__name__ if call.excinfo is not None else None
        status = report.outcome
        if report.failed and report.when != "call":
            status = "error"
        message = ""
        if report.failed:
            crash = getattr(report.longrepr, "reprcrash", None)
            message = (getattr(crash, "message", "") or str(report.longrepr))[-800:]
        _RESULTS.append(
            {
                "nodeid": report.nodeid,
                "outcome": status,
                "phase": report.when,
                "exc_type": exc_type,
                "message": message,
            }
        )


def pytest_collectreport(report):
    if report.failed:
        _RESULTS.append(
            {
                "nodeid": report.nodeid or "<collection>",
                "outcome": "error",
                "phase": "collect",
                "exc_type": "CollectionError",
                "message": str(report.longrepr)[-800:],
            }
        )


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("CR_REPORT_PATH")
    if not path and os.environ.get("SANDBOX_OUT"):  # security_agents drivers collect /out
        path = os.path.join(os.environ["SANDBOX_OUT"], "cr_report.json")
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"exitstatus": int(exitstatus), "cases": _RESULTS}, fh)
