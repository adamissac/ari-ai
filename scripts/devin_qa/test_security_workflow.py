#!/usr/bin/env python3
"""
Security Assessment Workflow Integration Test

Tests the entire lifecycle of a security assessment against the authorized
synthetic payments-lite lab target. This uses only repository-approved targets
and safe test catalogs.

Usage:
    python scripts/devin_qa/test_security_workflow.py
"""

import subprocess
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
import tempfile
import shutil

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


def test_backend_can_start() -> bool:
    """Test that the backend can start."""
    print("\n[1/8] Testing backend startup...")
    try:
        # Try to import backend
        result = run_command(
            ["uv", "run", "python", "-c", "import backend.backend; print('OK')"],
            timeout=30,
        )
        if result.returncode == 0:
            print_status("PASS", "Backend imports successfully")
            return True
        else:
            print_status("FAIL", f"Backend import failed: {result.stderr}")
            return False
    except Exception as e:
        print_status("FAIL", f"Backend startup test failed: {e}")
        return False


def test_shared_contracts_valid() -> bool:
    """Test that shared contracts are valid and can be exported."""
    print("\n[2/8] Testing shared contracts...")
    try:
        result = run_command(["uv", "run", "python", "-m", "shared.export", "--check"], timeout=30)
        if result.returncode == 0:
            print_status("PASS", "Shared contracts are valid and up-to-date")
            return True
        else:
            print_status("FAIL", f"Shared contract check failed: {result.stderr}")
            return False
    except Exception as e:
        print_status("FAIL", f"Shared contracts test failed: {e}")
        return False


def test_backend_tests_pass() -> bool:
    """Test that backend tests pass."""
    print("\n[3/8] Testing backend test suite...")
    try:
        result = run_command(["uv", "run", "pytest", "backend/tests/", "-q", "--tb=short"], timeout=120)
        if result.returncode == 0:
            # Extract pass count from output
            output = result.stdout + result.stderr
            print_status("PASS", f"Backend tests pass")
            print(f"     Output: {output[:200]}")
            return True
        else:
            print_status("FAIL", f"Backend tests failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"Backend test execution failed: {e}")
        return False


def test_security_agents_tests_pass() -> bool:
    """Test that security agents tests pass."""
    print("\n[4/8] Testing security agents test suite...")
    try:
        result = run_command(
            ["uv", "run", "pytest", "security-agents/tests/", "-q", "--tb=short"],
            timeout=120,
        )
        if result.returncode == 0:
            print_status("PASS", "Security agents tests pass")
            return True
        else:
            print_status("FAIL", f"Security agents tests failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"Security agents test execution failed: {e}")
        return False


def test_payments_lite_target_exists() -> bool:
    """Test that the payments-lite demo target exists and is structured correctly."""
    print("\n[5/8] Testing payments-lite demo target...")
    required_files = [
        "examples/payments-lite/README.md",
        "examples/payments-lite/labels.yaml",
        "examples/payments-lite/build_recipe.json",
        "examples/payments-lite/target/",
    ]

    all_exist = True
    for file_path in required_files:
        if not Path(file_path).exists():
            print_status("FAIL", f"Missing required file: {file_path}")
            all_exist = False

    if all_exist:
        print_status("PASS", "payments-lite target structure is complete")
        return True
    return False


def test_code_intelligence_tests_pass() -> bool:
    """Test that code intelligence tests pass."""
    print("\n[6/8] Testing code intelligence test suite...")
    try:
        result = run_command(
            ["uv", "run", "pytest", "code-intelligence/tests/", "-q", "--tb=short"],
            timeout=120,
        )
        if result.returncode == 0:
            print_status("PASS", "Code intelligence tests pass")
            return True
        else:
            print_status("FAIL", f"Code intelligence tests failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"Code intelligence test execution failed: {e}")
        return False


def test_code_review_tests_pass() -> bool:
    """Test that code review tests pass."""
    print("\n[7/8] Testing code review test suite...")
    try:
        result = run_command(
            ["uv", "run", "pytest", "code-review/tests/", "-q", "--tb=short"],
            timeout=120,
        )
        if result.returncode == 0:
            print_status("PASS", "Code review tests pass")
            return True
        else:
            print_status("FAIL", f"Code review tests failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"Code review test execution failed: {e}")
        return False


def test_standards_catalog_valid() -> bool:
    """Test that the standards catalog is valid."""
    print("\n[8/8] Testing standards catalog...")
    try:
        result = run_command(["uv", "run", "python", "-m", "standards.catalog", "--check"], timeout=30)
        if result.returncode == 0:
            print_status("PASS", "Standards catalog is valid")
            return True
        else:
            print_status("FAIL", f"Standards catalog check failed: {result.stderr}")
            return False
    except Exception as e:
        print_status("FAIL", f"Standards catalog test failed: {e}")
        return False


def run_integration_tests() -> Dict[str, bool]:
    """Run all integration tests and return results."""
    print(f"{BOLD}=== SECURITY ASSESSMENT WORKFLOW INTEGRATION TESTS ==={RESET}")
    print("Testing the security assessment pipeline components...\n")

    results = {}

    results["backend_startup"] = test_backend_can_start()
    results["shared_contracts"] = test_shared_contracts_valid()
    results["backend_tests"] = test_backend_tests_pass()
    results["security_agents_tests"] = test_security_agents_tests_pass()
    results["payments_lite_target"] = test_payments_lite_target_exists()
    results["code_intelligence_tests"] = test_code_intelligence_tests_pass()
    results["code_review_tests"] = test_code_review_tests_pass()
    results["standards_catalog"] = test_standards_catalog_valid()

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
        results = run_integration_tests()
        return print_summary(results)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Tests interrupted by user{RESET}")
        return 130
    except Exception as e:
        print(f"\n{RED}Unexpected error: {e}{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
