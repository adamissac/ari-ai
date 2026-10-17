#!/usr/bin/env python3
"""Run preflight and existing suites, preserving failed and incomplete outcomes."""

import argparse
import sys

from common import ROOT, report, run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args(argv)
    results = []
    for script in (
        "preflight_check.py",
        "test_security_workflow.py",
        "test_rl_workflow.py",
        "test_frontend_integration.py",
    ):
        command = [sys.executable, str(ROOT / "scripts/devin_qa" / script)]
        if script == "test_frontend_integration.py" and args.browser:
            command.append("--browser")
        result = run(script, command, timeout=3600, incomplete_exit=True)
        results.append(result)
    return report(results)


if __name__ == "__main__":
    raise SystemExit(main())
