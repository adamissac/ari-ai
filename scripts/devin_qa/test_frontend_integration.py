#!/usr/bin/env python3
"""Run frontend checks; --browser additionally starts the real local test stack."""

import argparse
import sys

from common import ROOT, Result, report, run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args(argv)
    frontend = ROOT / "frontend"
    if (
        not (frontend / "node_modules").is_dir()
        or not (frontend / "transport/node_modules").is_dir()
    ):
        return report(
            [Result("Frontend", "SKIP", "Run npm ci in frontend and frontend/transport first")]
        )
    results = [
        run("Transport build", ["npm", "run", "build"], cwd=frontend / "transport"),
        run("TypeScript", ["npm", "run", "typecheck"], cwd=frontend),
        run("ESLint", ["npm", "run", "lint"], cwd=frontend),
        run("Frontend unit tests", ["npm", "test"], cwd=frontend),
    ]
    if args.browser:
        results.append(
            run("Real-stack browser", [sys.executable, "tests/e2e/stack.py"], cwd=frontend)
        )
    else:
        results.append(
            Result(
                "Browser integration",
                "SKIP",
                "Use --browser; static checks do not prove API/browser integration",
            )
        )
    return report(results)


if __name__ == "__main__":
    raise SystemExit(main())
