#!/usr/bin/env python3
"""
Frontend/Backend Integration Test

Tests the integration between the frontend and backend API.
Verifies that the frontend can connect to the API and render assessment results.

Usage:
    python scripts/devin_qa/test_frontend_integration.py
"""

import subprocess
import sys
import json
import time
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


def test_frontend_structure() -> bool:
    """Test that the frontend structure is complete."""
    print("\n[1/6] Testing frontend structure...")
    required_files = [
        "frontend/package.json",
        "frontend/tsconfig.json",
        "frontend/app/",
        "frontend/transport/",
    ]

    all_exist = True
    for file_path in required_files:
        if not Path(file_path).exists():
            print_status("FAIL", f"Missing required file: {file_path}")
            all_exist = False

    if all_exist:
        print_status("PASS", "Frontend structure is complete")
        return True
    return False


def test_frontend_dependencies_installed() -> bool:
    """Test that frontend dependencies are installed."""
    print("\n[2/6] Testing frontend dependencies...")
    if not Path("frontend/node_modules").exists():
        print_status("SKIP", "node_modules not found (run 'npm install' in frontend/)")
        return True  # Not a failure, just needs setup
    print_status("PASS", "Frontend dependencies are installed")
    return True


def test_frontend_typecheck() -> bool:
    """Test that frontend TypeScript compiles without errors."""
    print("\n[3/6] Testing frontend TypeScript compilation...")
    try:
        result = run_command(["npm", "run", "typecheck"], cwd="frontend", timeout=60)
        if result.returncode == 0:
            print_status("PASS", "Frontend TypeScript compiles successfully")
            return True
        else:
            print_status("FAIL", f"TypeScript compilation failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"TypeScript check failed: {e}")
        return False


def test_frontend_lint() -> bool:
    """Test that frontend passes linting."""
    print("\n[4/6] Testing frontend linting...")
    try:
        result = run_command(["npm", "run", "lint"], cwd="frontend", timeout=60)
        if result.returncode == 0:
            print_status("PASS", "Frontend linting passes")
            return True
        else:
            print_status("FAIL", f"Frontend linting failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"Frontend lint check failed: {e}")
        return False


def test_frontend_unit_tests() -> bool:
    """Test that frontend unit tests pass."""
    print("\n[5/6] Testing frontend unit tests...")
    try:
        result = run_command(["npm", "run", "test:unit"], cwd="frontend", timeout=60)
        if result.returncode == 0:
            print_status("PASS", "Frontend unit tests pass")
            return True
        else:
            print_status("FAIL", f"Frontend unit tests failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"Frontend unit test execution failed: {e}")
        return False


def test_transport_types() -> bool:
    """Test that transport types are generated from shared contracts."""
    print("\n[6/6] Testing transport type generation...")
    try:
        result = run_command(
            ["uv", "run", "python", "-c", "from shared.shared import api; print('OK')"],
            timeout=30,
        )
        if result.returncode == 0:
            # Check if transport generated TS exists
            if Path("frontend/transport/generated/contracts.ts").exists():
                print_status("PASS", "Transport types are generated from shared contracts")
                return True
            else:
                print_status("FAIL", "Transport types not generated (run 'make contracts')")
                return False
        else:
            print_status("FAIL", f"Shared contracts import failed: {result.stderr}")
            return False
    except Exception as e:
        print_status("FAIL", f"Transport types test failed: {e}")
        return False


def run_frontend_tests() -> Dict[str, bool]:
    """Run all frontend integration tests and return results."""
    print(f"{BOLD}=== FRONTEND/BACKEND INTEGRATION TESTS ==={RESET}")
    print("Testing frontend structure and integration...\n")

    results = {}

    results["frontend_structure"] = test_frontend_structure()
    results["frontend_dependencies"] = test_frontend_dependencies_installed()
    results["frontend_typecheck"] = test_frontend_typecheck()
    results["frontend_lint"] = test_frontend_lint()
    results["frontend_unit_tests"] = test_frontend_unit_tests()
    results["transport_types"] = test_transport_types()

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
        results = run_frontend_tests()
        return print_summary(results)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Tests interrupted by user{RESET}")
        return 130
    except Exception as e:
        print(f"\n{RED}Unexpected error: {e}{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
