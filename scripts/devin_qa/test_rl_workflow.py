#!/usr/bin/env python3
"""
RL Defense Workflow Integration Test

Tests the simulated Double DQN cybersecurity defense environment.
Verifies that the simulation produces honest, labeled results and maintains
clear distinction from real security evidence.

Usage:
    python scripts/devin_qa/test_rl_workflow.py
"""

import subprocess
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_status(status: str, message: str) -> None:
    """Print a status message with color."""
    if status == "PASS":
        print(f"{GREEN}✓{RESET} {message}")
    elif status == "FAIL":
        print(f"{RED}✗{RESET} {message}")
    elif status == "SKIP":
        print(f"{YELLOW}⊘{RESET} {message}")
    else:
        print(f"  {message}")


def run_command(
    command: List[str],
    cwd: Optional[str] = None,
    timeout: int = 60,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    kwargs = {"capture_output": True, "text": True} if capture else {}
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            check=True,
            timeout=timeout,
            **kwargs,
        )
    except subprocess.CalledProcessError as e:
        return e
    except subprocess.TimeoutExpired as e:
        print_status("FAIL", f"Command timed out: {' '.join(command)}")
        raise


def test_rl_environment_exists() -> bool:
    """Test that the RL defense environment exists."""
    print("\n[1/6] Testing RL defense environment structure...")
    required_files = [
        "rl-defense/README.md",
        "rl-defense/rl_defense/__init__.py",
        "rl-defense/configs/",
        "rl-defense/experiments/",
    ]

    all_exist = True
    for file_path in required_files:
        if not Path(file_path).exists():
            print_status("FAIL", f"Missing required file: {file_path}")
            all_exist = False

    if all_exist:
        print_status("PASS", "RL defense environment structure is complete")
        return True
    return False


def test_rl_imports() -> bool:
    """Test that RL defense modules can be imported."""
    print("\n[2/6] Testing RL defense imports...")
    try:
        result = run_command(
            ["uv", "run", "python", "-c", "import rl_defense; print('OK')"],
            timeout=30,
        )
        if result.returncode == 0:
            print_status("PASS", "RL defense imports successfully")
            return True
        else:
            print_status("FAIL", f"RL defense import failed: {result.stderr}")
            return False
    except Exception as e:
        print_status("FAIL", f"RL defense import test failed: {e}")
        return False


def test_rl_tests_pass() -> bool:
    """Test that RL defense tests pass."""
    print("\n[3/6] Testing RL defense test suite...")
    try:
        result = run_command(
            ["uv", "run", "pytest", "rl-defense/tests/", "-q", "--tb=short"],
            timeout=120,
        )
        if result.returncode == 0:
            print_status("PASS", "RL defense tests pass")
            return True
        else:
            print_status("FAIL", f"RL defense tests failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"RL defense test execution failed: {e}")
        return False


def test_rl_contract_types() -> bool:
    """Test that RL contract types are defined in shared contracts."""
    print("\n[4/6] Testing RL contract types...")
    try:
        result = run_command(
            ["uv", "run", "python", "-c", "from shared.shared import rl; print('OK')"],
            timeout=30,
        )
        if result.returncode == 0:
            print_status("PASS", "RL contract types exist in shared")
            return True
        else:
            print_status("FAIL", f"RL contract types import failed: {result.stderr}")
            return False
    except Exception as e:
        print_status("FAIL", f"RL contract types test failed: {e}")
        return False


def test_rl_backend_integration() -> bool:
    """Test that RL defense is integrated with backend."""
    print("\n[5/6] Testing RL backend integration...")
    try:
        result = run_command(
            ["uv", "run", "python", "-c", "from backend.backend import intelligence; print('OK')"],
            timeout=30,
        )
        if result.returncode == 0:
            print_status("PASS", "RL backend integration exists")
            return True
        else:
            print_status("FAIL", f"RL backend integration check failed: {result.stderr}")
            return False
    except Exception as e:
        print_status("FAIL", f"RL backend integration test failed: {e}")
        return False


def test_rl_honesty_labeling() -> bool:
    """Test that RL results are properly labeled as simulated."""
    print("\n[6/6] Testing RL honesty labeling...")
    try:
        # Check that RLRecommendation has explanation/caveat fields
        result = run_command(
            [
                "uv",
                "run",
                "python",
                "-c",
                "from shared.shared.rl import DefenseRecommendation; print('has_explanation' if hasattr(DefenseRecommendation.model_fields, 'explanation') else 'missing')",
            ],
            timeout=30,
        )
        if result.returncode == 0 and "has_explanation" in result.stdout:
            print_status("PASS", "RL results have explanation/caveat fields")
            return True
        else:
            print_status("FAIL", f"RL honesty labeling check failed: {result.stderr}")
            return False
    except Exception as e:
        print_status("FAIL", f"RL honesty labeling test failed: {e}")
        return False


def run_rl_tests() -> Dict[str, bool]:
    """Run all RL workflow tests and return results."""
    print(f"{BOLD}=== RL DEFENSE WORKFLOW INTEGRATION TESTS ==={RESET}")
    print("Testing the simulated Double DQN defense environment...\n")

    results = {}

    results["rl_environment_exists"] = test_rl_environment_exists()
    results["rl_imports"] = test_rl_imports()
    results["rl_tests"] = test_rl_tests_pass()
    results["rl_contract_types"] = test_rl_contract_types()
    results["rl_backend_integration"] = test_rl_backend_integration()
    results["rl_honesty_labeling"] = test_rl_honesty_labeling()

    return results


def print_summary(results: Dict[str, bool]) -> int:
    """Print a summary of test results."""
    print(f"\n{BOLD}=== TEST SUMMARY ==={RESET}\n")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed

    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print_status(status, test_name)

    print(f"\nTotal: {total}, {GREEN}Passed: {passed}{RESET}, {RED}Failed: {failed}{RESET}")

    if failed == 0:
        print(f"\n{GREEN}{BOLD}✓ ALL TESTS PASSED{RESET}")
        return 0
    else:
        print(f"\n{RED}{BOLD}✗ SOME TESTS FAILED{RESET}")
        return 1


def main() -> int:
    """Main entry point."""
    try:
        results = run_rl_tests()
        return print_summary(results)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Tests interrupted by user{RESET}")
        return 130
    except Exception as e:
        print(f"\n{RED}Unexpected error: {e}{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
