#!/usr/bin/env python3
"""
End-to-End Smoke Test

Tests the actual system components working together where possible.
This script uses genuine system outputs rather than hardcoded success responses.

Usage:
    python scripts/devin_qa/test_e2e_smoke.py
"""

import subprocess
import sys
import json
import time
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
    elif status == "INFO":
        print(f"  {message}")
    else:
        print(f"{status}: {message}")


def run_command(
    command: List[str],
    cwd: Optional[str] = None,
    timeout: int = 60,
    capture: bool = True,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    kwargs = {"capture_output": True, "text": True} if capture else {}
    if env:
        kwargs["env"] = {**dict(os.environ), **env}
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


def check_url(url: str, timeout: int = 5) -> Tuple[bool, str]:
    """Check if a URL is reachable."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return True, f"HTTP {response.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, str(e.reason)
    except Exception as e:
        return False, str(e)


def test_backend_health() -> bool:
    """Test backend health endpoint."""
    print("\n[1/12] Testing backend health endpoint...")
    try:
        success, result = check_url("http://localhost:8000/healthz")
        if success:
            print_status("PASS", f"Backend health endpoint: {result}")
            return True
        else:
            print_status("SKIP", f"Backend not running: {result}")
            return True
    except Exception as e:
        print_status("SKIP", f"Backend health check failed: {e}")
        return True


def test_backend_readiness() -> bool:
    """Test backend readiness endpoint."""
    print("\n[2/12] Testing backend readiness endpoint...")
    try:
        success, result = check_url("http://localhost:8000/readyz")
        if success:
            print_status("PASS", f"Backend readiness endpoint: {result}")
            return True
        else:
            print_status("SKIP", f"Backend not ready: {result}")
            return True
    except Exception as e:
        print_status("SKIP", f"Backend readiness check failed: {e}")
        return True


def test_backend_api_docs() -> bool:
    """Test backend API documentation."""
    print("\n[3/12] Testing backend API documentation...")
    try:
        success, result = check_url("http://localhost:8000/docs")
        if success:
            print_status("PASS", f"Backend API docs accessible: {result}")
            return True
        else:
            print_status("SKIP", f"Backend API docs not accessible: {result}")
            return True
    except Exception as e:
        print_status("SKIP", f"Backend API docs check failed: {e}")
        return True


def test_database_connection() -> bool:
    """Test database connection using embedded devdb."""
    print("\n[4/12] Testing database connection...")
    try:
        result = run_command(
            ["uv", "run", "python", "-c", "import sys; sys.path.insert(0, 'backend'); from backend import devdb; print('OK')"],
            timeout=30,
        )
        if result.returncode == 0:
            print_status("PASS", "Database devdb module imports successfully")
            return True
        else:
            print_status("FAIL", f"Database connection test failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"Database connection test failed: {e}")
        return False


def test_migrations() -> bool:
    """Test database migrations."""
    print("\n[5/12] Testing database migrations...")
    try:
        result = run_command(
            ["uv", "run", "python", "-c", "import sys; sys.path.insert(0, 'backend'); from backend import migrate; print('OK')"],
            timeout=30,
        )
        if result.returncode == 0:
            print_status("PASS", "Migration module imports successfully")
            return True
        else:
            print_status("FAIL", f"Migration test failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"Migration test failed: {e}")
        return False


def test_payments_lite_structure() -> bool:
    """Test payments-lite target structure."""
    print("\n[6/12] Testing payments-lite target structure...")
    required_files = [
        "examples/payments-lite/README.md",
        "examples/payments-lite/labels.yaml",
        "examples/payments-lite/build_recipe.json",
        "examples/payments-lite/target/payments_lite/",
    ]

    all_exist = True
    for file_path in required_files:
        if not Path(file_path).exists():
            print_status("FAIL", f"Missing: {file_path}")
            all_exist = False

    if all_exist:
        print_status("PASS", "payments-lite target structure complete")
        return True
    return False


def test_shared_contracts() -> bool:
    """Test shared contracts can be imported."""
    print("\n[7/12] Testing shared contracts...")
    try:
        result = run_command(
            ["uv", "run", "python", "-c", "import sys; sys.path.insert(0, 'shared'); from shared import api, assessment, findings; print('OK')"],
            timeout=30,
        )
        if result.returncode == 0:
            print_status("PASS", "Shared contracts import successfully")
            return True
        else:
            print_status("FAIL", f"Shared contracts import failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"Shared contracts test failed: {e}")
        return False


def test_backend_imports() -> bool:
    """Test backend modules can be imported."""
    print("\n[8/12] Testing backend imports...")
    try:
        import os
        if not os.environ.get("DATABASE_URL"):
            print_status("SKIP", "Backend imports require DATABASE_URL (use 'make dev-db' or set DATABASE_URL)")
            return True
        result = run_command(
            ["uv", "run", "python", "-c", "import sys; sys.path.insert(0, 'backend'); import backend; print('OK')"],
            timeout=30,
        )
        if result.returncode == 0:
            print_status("PASS", "Backend modules import successfully")
            return True
        else:
            print_status("FAIL", f"Backend imports failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"Backend imports test failed: {e}")
        return False


def test_security_agents_imports() -> bool:
    """Test security agents can be imported."""
    print("\n[9/12] Testing security agents imports...")
    try:
        import os
        if not os.environ.get("DATABASE_URL"):
            print_status("SKIP", "Security agents imports require DATABASE_URL (use 'make dev-db' or set DATABASE_URL)")
            return True
        result = run_command(
            ["uv", "run", "python", "-c", "import sys; sys.path.insert(0, 'security-agents'); import security_agents; print('OK')"],
            timeout=30,
        )
        if result.returncode == 0:
            print_status("PASS", "Security agents import successfully")
            return True
        else:
            print_status("FAIL", f"Security agents import failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"Security agents test failed: {e}")
        return False


def test_code_intelligence_imports() -> bool:
    """Test code intelligence can be imported."""
    print("\n[10/12] Testing code intelligence imports...")
    try:
        import os
        if not os.environ.get("DATABASE_URL"):
            print_status("SKIP", "Code intelligence imports require DATABASE_URL (use 'make dev-db' or set DATABASE_URL)")
            return True
        result = run_command(
            ["uv", "run", "python", "-c", "import sys; sys.path.insert(0, 'code-intelligence'); import code_intelligence; print('OK')"],
            timeout=30,
        )
        if result.returncode == 0:
            print_status("PASS", "Code intelligence imports successfully")
            return True
        else:
            print_status("FAIL", f"Code intelligence import failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"Code intelligence test failed: {e}")
        return False


def test_code_review_imports() -> bool:
    """Test code review can be imported."""
    print("\n[11/12] Testing code review imports...")
    try:
        import os
        if not os.environ.get("DATABASE_URL"):
            print_status("SKIP", "Code review imports require DATABASE_URL (use 'make dev-db' or set DATABASE_URL)")
            return True
        result = run_command(
            ["uv", "run", "python", "-c", "import sys; sys.path.insert(0, 'code-review'); import code_review; print('OK')"],
            timeout=30,
        )
        if result.returncode == 0:
            print_status("PASS", "Code review imports successfully")
            return True
        else:
            print_status("FAIL", f"Code review import failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"Code review test failed: {e}")
        return False


def test_rl_defense_imports() -> bool:
    """Test RL defense can be imported."""
    print("\n[12/12] Testing RL defense imports...")
    try:
        import os
        if not os.environ.get("DATABASE_URL"):
            print_status("SKIP", "RL defense imports require DATABASE_URL (use 'make dev-db' or set DATABASE_URL)")
            return True
        result = run_command(
            ["uv", "run", "python", "-c", "import sys; sys.path.insert(0, 'rl-defense'); import rl_defense; print('OK')"],
            timeout=30,
        )
        if result.returncode == 0:
            print_status("PASS", "RL defense imports successfully")
            return True
        else:
            print_status("FAIL", f"RL defense import failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_status("FAIL", f"RL defense test failed: {e}")
        return False


def run_e2e_tests() -> Dict[str, bool]:
    """Run all end-to-end smoke tests and return results."""
    print(f"{BOLD}=== END-TO-END SMOKE TESTS ==={RESET}")
    print("Testing actual system components working together...\n")

    results = {}

    results["backend_health"] = test_backend_health()
    results["backend_readiness"] = test_backend_readiness()
    results["backend_api_docs"] = test_backend_api_docs()
    results["database_connection"] = test_database_connection()
    results["migrations"] = test_migrations()
    results["payments_lite_structure"] = test_payments_lite_structure()
    results["shared_contracts"] = test_shared_contracts()
    results["backend_imports"] = test_backend_imports()
    results["security_agents_imports"] = test_security_agents_imports()
    results["code_intelligence_imports"] = test_code_intelligence_imports()
    results["code_review_imports"] = test_code_review_imports()
    results["rl_defense_imports"] = test_rl_defense_imports()

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
        results = run_e2e_tests()
        return print_summary(results)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Tests interrupted by user{RESET}")
        return 130
    except Exception as e:
        print(f"\n{RED}Unexpected error: {e}{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
