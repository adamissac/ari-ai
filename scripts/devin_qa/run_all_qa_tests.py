#!/usr/bin/env python3
"""
Master QA Test Runner

Runs all QA test suites in sequence and aggregates results.

Usage:
    python scripts/devin_qa/run_all_qa_tests.py
"""

import subprocess
import sys
from pathlib import Path

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(title: str) -> None:
    """Print a section header."""
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}{title}{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")


def run_test_suite(script_name: str, suite_name: str) -> int:
    """Run a test suite and return the exit code."""
    script_path = Path(__file__).parent / script_name
    if not script_path.exists():
        print(f"{RED}Test script not found: {script_path}{RESET}")
        return 1

    print_header(f"Running: {suite_name}")
    result = subprocess.run(["python3", str(script_path)], cwd=Path(__file__).parent.parent.parent)
    return result.returncode


def main() -> int:
    """Main entry point."""
    print(f"{BOLD}=== MASTER QA TEST RUNNER ==={RESET}")
    print("Running all QA test suites...\n")

    # Change to repository root
    repo_root = Path(__file__).parent.parent.parent
    import os
    os.chdir(repo_root)

    results = {}

    # Run preflight check
    results["Preflight Check"] = run_test_suite("preflight_check.py", "Demo Preflight Check")

    # Run security workflow tests
    results["Security Workflow"] = run_test_suite("test_security_workflow.py", "Security Assessment Workflow Tests")

    # Run RL workflow tests
    results["RL Workflow"] = run_test_suite("test_rl_workflow.py", "RL Defense Workflow Tests")

    # Run frontend integration tests
    results["Frontend Integration"] = run_test_suite("test_frontend_integration.py", "Frontend/Backend Integration Tests")

    # Print overall summary
    print_header("OVERALL SUMMARY")

    total = len(results)
    passed = sum(1 for v in results.values() if v == 0)
    failed = total - passed

    for suite_name, exit_code in results.items():
        status = f"{GREEN}PASS{RESET}" if exit_code == 0 else f"{RED}FAIL{RESET}"
        print(f"{status}: {suite_name}")

    print(f"\nTotal suites: {total}")
    print(f"{GREEN}Passed: {passed}{RESET}")
    print(f"{RED}Failed: {failed}{RESET}")

    if failed == 0:
        print(f"\n{GREEN}{BOLD}✓ ALL QA TEST SUITES PASSED{RESET}")
        return 0
    else:
        print(f"\n{RED}{BOLD}✗ SOME QA TEST SUITES FAILED{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
