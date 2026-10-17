#!/usr/bin/env python3
"""
M7 Demo Validation Script

Executes the genuine end-to-end M7 workflow using the repository's
authorized payments-lite demonstration target.

This script:
- Validates prerequisites
- Lets the backend test fixture manage its isolated PostgreSQL database
- Executes the supported core M7 workflow
- Waits for completion with bounded timeouts
- Confirms persisted results
- Verifies evidence references
- Distinguishes passed, failed, skipped, and blocked stages
- Saves a JSON report with bounded test output excerpts
- Exits nonzero when any required stage fails
- Avoids real API charges by default
- Cleans up only resources created by the test

Usage:
    python3 scripts/devin_qa/verify_m7_demo.py
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_status(status: str, message: str) -> None:
    """Print a status message with color."""
    if status == "PASS":
        print(f"{GREEN}✓{RESET} {message}")
    elif status == "FAIL":
        print(f"{RED}✗{RESET} {message}")
    elif status == "SKIP":
        print(f"{BLUE}⊘{RESET} {message}")
    elif status == "BLOCKED":
        print(f"{YELLOW}⚠{RESET} {message}")
    else:
        print(f"  {message}")


def run_command(
    command: list[str],
    cwd: Path | None = None,
    timeout: int = 900,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        merged_env = dict(os.environ)
        if env:
            merged_env.update(env)
        merged_env["RUN_LIVE_LLM_EVAL"] = "0"

        result = subprocess.run(
            command,
            cwd=cwd or ROOT,
            env=merged_env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".dev/qa/m7-evidence.json")
    args = parser.parse_args(argv)
    print(f"{BOLD}=== M7 DEMO VALIDATION ==={RESET}")
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")
    print(f"Repository: {ROOT}\n")

    results = []

    # === Stage 1: Prerequisites ===
    print(f"{BOLD}=== Stage 1: Prerequisites ==={RESET}")

    # Check Python
    code, stdout, _ = run_command([sys.executable, "--version"])
    if code == 0:
        print_status("PASS", f"Python available: {stdout.strip()}")
        results.append({"stage": "prerequisites", "check": "python", "status": "PASS"})
    else:
        print_status("FAIL", "Python not available")
        results.append({"stage": "prerequisites", "check": "python", "status": "FAIL"})

    # === Stage 2: Run M7 Test ===
    print(f"\n{BOLD}=== Stage 2: Execute M7 Test ==={RESET}")
    print("Running backend/tests/test_m7_push_to_regression.py...\n")

    # conftest creates and drops a session-specific database. Do not start or stop
    # backend.devdb's default server: it may belong to an active development stack.
    test_env = {
        "PYTHONPATH": os.pathsep.join(
            str(ROOT / package)
            for package in (
                "backend",
                "shared",
                "security-agents",
                "code-review",
                "code-intelligence",
                "monitoring",
                "standards",
            )
        ),
    }
    code, stdout, stderr = run_command(
        [sys.executable, "-m", "pytest", "-q", "backend/tests/test_m7_push_to_regression.py", "-s"],
        timeout=1200,
        env=test_env,
        cwd=ROOT,
    )

    if code == 0:
        print_status("PASS", "M7 test passed - full chain executed successfully")
        results.append(
            {
                "stage": "m7_execution",
                "check": "full_chain",
                "status": "PASS",
                "output": stdout[:500],
            }
        )
    else:
        print_status("FAIL", f"M7 test failed with exit code {code}")
        print(f"Stdout: {stdout[:500]}")
        print(f"Stderr: {stderr[:500]}")
        results.append(
            {
                "stage": "m7_execution",
                "check": "full_chain",
                "status": "FAIL",
                "exit_code": code,
                "output": stdout[:1000],
                "error": stderr[:1000],
            }
        )

    # === Stage 3: Browser Demo ===
    print(f"\n{BOLD}=== Stage 3: Browser Demo ==={RESET}")
    print("Checking for Playwright browser tests...\n")

    # Check if Playwright test exists
    playwright_test = ROOT / "frontend" / "tests" / "e2e" / "stack.py"
    if playwright_test.exists():
        print("Playwright test found - BLOCKED (not executed by this backend-only validation)")
        results.append(
            {
                "stage": "browser_demo",
                "check": "playwright",
                "status": "BLOCKED",
                "reason": "Browser E2E was not selected; run frontend/tests/e2e/stack.py (it starts its own test services)",
            }
        )
    else:
        print_status("BLOCKED", "Playwright test not found at frontend/tests/e2e/stack.py")
        results.append(
            {
                "stage": "browser_demo",
                "check": "playwright",
                "status": "BLOCKED",
                "reason": "Test file not found",
            }
        )

    # === Save Report ===
    print(f"\n{BOLD}=== Saving Report ==={RESET}")

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "repository": str(ROOT),
        "results": results,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r["status"] == "PASS"),
            "failed": sum(1 for r in results if r["status"] == "FAIL"),
            "skipped": sum(1 for r in results if r["status"] == "SKIP"),
            "blocked": sum(1 for r in results if r["status"] == "BLOCKED"),
        },
    }

    report_path = args.output
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Report saved to: {report_path}")

    # === Print Summary ===
    print(f"\n{BOLD}=== SUMMARY ==={RESET}")
    print(f"Total checks: {report['summary']['total']}")
    print(f"{GREEN}Passed: {report['summary']['passed']}{RESET}")
    print(f"{RED}Failed: {report['summary']['failed']}{RESET}")
    print(f"{BLUE}Skipped: {report['summary']['skipped']}{RESET}")
    print(f"{YELLOW}Blocked: {report['summary']['blocked']}{RESET}")

    if report["summary"]["failed"] > 0:
        print(f"\n{RED}{BOLD}✗ M7 DEMO VALIDATION FAILED{RESET}")
        return 1
    elif report["summary"]["blocked"] > 0:
        print(f"\n{YELLOW}{BOLD}⚠ M7 DEMO VALIDATION INCOMPLETE (blocked stages) {RESET}")
        return 2
    else:
        print(f"\n{GREEN}{BOLD}✓ M7 DEMO VALIDATION PASSED{RESET}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
