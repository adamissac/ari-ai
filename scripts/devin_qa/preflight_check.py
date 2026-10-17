#!/usr/bin/env python3
"""Read-only local prerequisites and API readiness; never declares a demo verified."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import asdict

from common import ROOT, Result, exit_code, report


def readiness(url: str) -> Result:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/readyz", timeout=5) as response:
            data = json.load(response)
        if not isinstance(data, dict) or not all(
            data.get(k) is True for k in ("database", "queue", "webhook_secret_configured")
        ):
            return Result(
                "API readiness",
                "FAIL",
                "Database, queue and configured webhook secret must all report true",
            )
        return Result(
            "API readiness", "PASS", "Database, queue and configured webhook secret reported ready"
        )
    except urllib.error.HTTPError:
        return Result("API readiness", "FAIL", "API returned an HTTP error")
    except (urllib.error.URLError, TimeoutError, OSError):
        return Result(
            "API readiness", "SKIP", "Service unavailable; start the documented local stack"
        )
    except (ValueError, UnicodeError):
        return Result("API readiness", "FAIL", "API did not return valid readiness JSON")


def checks(api_url: str) -> list[Result]:
    results = [Result("Python 3.12+", "PASS" if sys.version_info >= (3, 12) else "FAIL")]
    for executable in ("git", "node", "npm", "docker"):
        results.append(
            Result(
                executable,
                "PASS" if shutil.which(executable) else "SKIP",
                "Executable availability only; service health is not implied",
            )
        )
    for package in (
        "backend",
        "shared",
        "security_agents",
        "code_intelligence",
        "code_review",
        "rl_defense",
    ):
        results.append(
            Result(
                package,
                "PASS" if importlib.util.find_spec(package) else "SKIP",
                "Package discoverability only",
            )
        )
    for file in (
        "uv.lock",
        "docker-compose.yml",
        "frontend/package.json",
        "examples/payments-lite/build_recipe.json",
    ):
        results.append(Result(file, "PASS" if (ROOT / file).is_file() else "FAIL"))
    results.append(readiness(api_url))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    results = checks(args.api_url)
    if args.json:
        print(json.dumps({"checks": [asdict(r) for r in results], "exit_code": exit_code(results)}))
        return exit_code(results)
    return report(results)


if __name__ == "__main__":
    raise SystemExit(main())
