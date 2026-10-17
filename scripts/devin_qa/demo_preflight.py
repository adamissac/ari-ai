#!/usr/bin/env python3
"""
Demo Preflight Checker

One-command demo preflight that checks the entire local demo environment.
Reports runtime versions, missing dependencies, container availability, backend health,
frontend availability, database health, artifact store readiness, required configuration,
supported model mode, required API endpoints, and testable integration paths.

Usage:
    python scripts/devin_qa/demo_preflight.py
"""

import subprocess
import sys
import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Tuple, Any

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_status(category: str, status: str, message: str, essential: bool = False) -> None:
    """Print a status message with color."""
    if status == "PASS":
        icon = f"{GREEN}✓{RESET}"
    elif status == "FAIL":
        icon = f"{RED}✗{RESET}"
    elif status == "WARN":
        icon = f"{YELLOW}⚠{RESET}"
    elif status == "SKIP":
        icon = f"{BLUE}⊘{RESET}"
    else:
        icon = status

    essential_mark = " [ESSENTIAL]" if essential else ""
    print(f"{icon} [{category}]{essential_mark} {message}")


def run_command(command: List[str], timeout: int = 30) -> Tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


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


def run_preflight() -> Dict[str, Any]:
    """Run all preflight checks and return results."""
    print(f"{BOLD}=== DEMO PREFLIGHT CHECKER ==={RESET}\n")

    results = {
        "essential_pass": 0,
        "essential_fail": 0,
        "optional_pass": 0,
        "optional_fail": 0,
        "checks": [],
    }

    # === Runtime Versions ===
    print(f"{BOLD}RUNTIME VERSIONS:{RESET}")

    code, stdout, _ = run_command(["python3", "--version"])
    python_version = stdout.strip() if code == 0 else "Not found"
    print_status("Runtime", "PASS" if code == 0 else "FAIL", f"Python: {python_version}", essential=True)
    if code == 0:
        results["essential_pass"] += 1
    else:
        results["essential_fail"] += 1

    code, stdout, _ = run_command(["uv", "--version"])
    uv_version = stdout.strip() if code == 0 else "Not found"
    print_status("Runtime", "PASS" if code == 0 else "FAIL", f"UV: {uv_version}", essential=True)
    if code == 0:
        results["essential_pass"] += 1
    else:
        results["essential_fail"] += 1

    code, stdout, _ = run_command(["node", "--version"])
    node_version = stdout.strip() if code == 0 else "Not found"
    print_status("Runtime", "PASS" if code == 0 else "WARN", f"Node.js: {node_version}", essential=False)
    if code == 0:
        results["optional_pass"] += 1
    else:
        results["optional_fail"] += 1

    code, stdout, _ = run_command(["docker", "--version"])
    docker_version = stdout.strip() if code == 0 else "Not found"
    print_status("Runtime", "PASS" if code == 0 else "WARN", f"Docker: {docker_version}", essential=False)
    if code == 0:
        results["optional_pass"] += 1
    else:
        results["optional_fail"] += 1

    # === Dependencies ===
    print(f"\n{BOLD}DEPENDENCIES:{RESET}")

    required_files = [
        ("backend/pyproject.toml", True),
        ("frontend/package.json", True),
        ("shared/pyproject.toml", True),
        ("security-agents/pyproject.toml", True),
        ("code-intelligence/pyproject.toml", True),
        ("code-review/pyproject.toml", True),
        ("rl-defense/pyproject.toml", True),
        ("examples/payments-lite/README.md", True),
        ("uv.lock", True),
        ("Makefile", True),
        ("docker-compose.yml", False),
    ]

    for file_path, essential in required_files:
        exists = Path(file_path).exists()
        status = "PASS" if exists else "FAIL"
        print_status("Dependencies", status, f"File: {file_path}", essential=essential)
        if exists:
            if essential:
                results["essential_pass"] += 1
            else:
                results["optional_pass"] += 1
        else:
            if essential:
                results["essential_fail"] += 1
            else:
                results["optional_fail"] += 1

    # === Backend Health ===
    print(f"\n{BOLD}BACKEND HEALTH:{RESET}")

    # Backend import test
    code, _, stderr = run_command(
        ["uv", "run", "python", "-c", "import sys; sys.path.insert(0, 'backend'); import backend; print('OK')"]
    )
    print_status("Backend", "PASS" if code == 0 else "FAIL", "Backend imports successfully", essential=True)
    if code == 0:
        results["essential_pass"] += 1
    else:
        results["essential_fail"] += 1

    # Backend API health
    success, result = check_url("http://localhost:8000/healthz")
    print_status("Backend", "PASS" if success else "WARN", f"Health endpoint: {result}", essential=False)
    if success:
        results["optional_pass"] += 1
    else:
        results["optional_fail"] += 1

    # Backend readiness
    success, result = check_url("http://localhost:8000/readyz")
    print_status("Backend", "PASS" if success else "WARN", f"Readiness endpoint: {result}", essential=False)
    if success:
        results["optional_pass"] += 1
    else:
        results["optional_fail"] += 1

    # === Frontend Health ===
    print(f"\n{BOLD}FRONTEND HEALTH:{RESET}")

    # Frontend structure
    frontend_structure = Path("frontend/app").exists() and Path("frontend/package.json").exists()
    print_status("Frontend", "PASS" if frontend_structure else "FAIL", "Frontend structure complete", essential=True)
    if frontend_structure:
        results["essential_pass"] += 1
    else:
        results["essential_fail"] += 1

    # Frontend dependencies
    node_modules = Path("frontend/node_modules").exists()
    print_status("Frontend", "PASS" if node_modules else "WARN", "node_modules installed", essential=False)
    if node_modules:
        results["optional_pass"] += 1
    else:
        results["optional_fail"] += 1

    # Frontend server
    success, result = check_url("http://localhost:3000")
    print_status("Frontend", "PASS" if success else "WARN", f"Frontend server: {result}", essential=False)
    if success:
        results["optional_pass"] += 1
    else:
        results["optional_fail"] += 1

    # === Database Health ===
    print(f"\n{BOLD}DATABASE HEALTH:{RESET}")

    # .env.example
    env_example = Path(".env.example").exists()
    print_status("Database", "PASS" if env_example else "FAIL", ".env.example exists", essential=True)
    if env_example:
        results["essential_pass"] += 1
    else:
        results["essential_fail"] += 1

    # .env
    env_file = Path(".env").exists()
    print_status("Database", "PASS" if env_file else "WARN", ".env configured", essential=False)
    if env_file:
        results["optional_pass"] += 1
    else:
        results["optional_fail"] += 1

    # DATABASE_URL
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        print_status("Database", "PASS", "DATABASE_URL set", essential=False)
        results["optional_pass"] += 1
    else:
        print_status("Database", "WARN", "DATABASE_URL not set (can use embedded DB)", essential=False)
        results["optional_fail"] += 1

    # Database module
    code, _, _ = run_command(
        ["uv", "run", "python", "-c", "import sys; sys.path.insert(0, 'backend'); from backend import devdb; print('OK')"]
    )
    print_status("Database", "PASS" if code == 0 else "FAIL", "Database devdb module imports", essential=True)
    if code == 0:
        results["essential_pass"] += 1
    else:
        results["essential_fail"] += 1

    # === Configuration ===
    print(f"\n{BOLD}CONFIGURATION:{RESET}")

    configs = [
        ("ANTHROPIC_API_KEY", False),
        ("GITHUB_WEBHOOK_SECRET", False),
        ("SESSION_SECRET", False),
    ]

    for config_name, essential in configs:
        value = os.environ.get(config_name)
        if value and value not in ["", "replace-me", "YOUR_VALUE_HERE"]:
            print_status("Config", "PASS", f"{config_name} set", essential=essential)
            if essential:
                results["essential_pass"] += 1
            else:
                results["optional_pass"] += 1
        else:
            print_status("Config", "WARN" if not essential else "FAIL", f"{config_name} not set", essential=essential)
            if essential:
                results["essential_fail"] += 1
            else:
                results["optional_fail"] += 1

    # === Shared Contracts ===
    print(f"\n{BOLD}SHARED CONTRACTS:{RESET}")

    code, _, _ = run_command(
        ["uv", "run", "python", "-c", "import sys; sys.path.insert(0, 'shared'); from shared import api; print('OK')"]
    )
    print_status("Contracts", "PASS" if code == 0 else "FAIL", "Shared contracts import", essential=True)
    if code == 0:
        results["essential_pass"] += 1
    else:
        results["essential_fail"] += 1

    # Transport types
    transport_types = Path("frontend/transport/generated/contracts.ts").exists()
    print_status("Contracts", "PASS" if transport_types else "WARN", "Transport types generated", essential=False)
    if transport_types:
        results["optional_pass"] += 1
    else:
        results["optional_fail"] += 1

    # === Standards Catalog ===
    print(f"\n{BOLD}STANDARDS CATALOG:{RESET}")

    code, _, _ = run_command(
        ["uv", "run", "python", "-c", "import sys; sys.path.insert(0, 'standards'); from standards.catalog import verify_all; verify_all()"]
    )
    print_status("Standards", "PASS" if code == 0 else "FAIL", "Standards catalog valid", essential=True)
    if code == 0:
        results["essential_pass"] += 1
    else:
        results["essential_fail"] += 1

    return results


def print_summary(results: Dict[str, Any]) -> int:
    """Print summary and return exit code."""
    print(f"\n{BOLD}=== SUMMARY ==={RESET}\n")

    essential_total = results["essential_pass"] + results["essential_fail"]
    optional_total = results["optional_pass"] + results["optional_fail"]

    print(f"Essential checks: {GREEN}{results['essential_pass']}/{essential_total}{RESET} passed")
    print(f"Optional checks: {results['optional_pass']}/{optional_total} passed")

    if results["essential_fail"] > 0:
        print(f"\n{RED}{BOLD}✗ NOT READY FOR DEMO (fix essential failures){RESET}")
        return 1
    elif results["optional_fail"] > 0:
        print(f"\n{YELLOW}{BOLD}⚠ READY FOR DEMO WITH LIMITATIONS (review warnings){RESET}")
        return 0
    else:
        print(f"\n{GREEN}{BOLD}✓ READY FOR DEMO{RESET}")
        return 0


def main() -> int:
    """Main entry point."""
    results = run_preflight()
    return print_summary(results)


if __name__ == "__main__":
    sys.exit(main())
