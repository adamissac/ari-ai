#!/usr/bin/env python3
"""
Demo Preflight Checker

Checks whether the demonstration environment is ready for a hackathon demo.
This script performs read-only checks against the system and reports PASS/FAIL/WARNING.

Usage:
    python scripts/devin_qa/preflight_check.py
"""

import subprocess
import sys
import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Tuple

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_status(status: str, message: str) -> None:
    """Print a status message with color."""
    if status == "PASS":
        print(f"{GREEN}✓ PASS{RESET}: {message}")
    elif status == "FAIL":
        print(f"{RED}✗ FAIL{RESET}: {message}")
    elif status == "WARN":
        print(f"{YELLOW}⚠ WARN{RESET}: {message}")
    else:
        print(f"{status}: {message}")


def check_command_exists(command: str) -> bool:
    """Check if a command exists in PATH."""
    try:
        subprocess.run(
            ["which", command],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def check_file_exists(path: str) -> bool:
    """Check if a file exists."""
    return Path(path).exists()


def check_url_reachable(url: str, timeout: int = 5) -> bool:
    """Check if a URL is reachable (HEAD request)."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status < 400
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return False


def check_environment_variable(var_name: str, required: bool = True) -> Tuple[bool, str]:
    """Check if an environment variable is set."""
    value = os.environ.get(var_name)
    if required and not value:
        return False, f"{var_name} is not set"
    if not value:
        return True, f"{var_name} is optional (not set)"
    if value in ["", "replace-me", "YOUR_VALUE_HERE"]:
        return False, f"{var_name} is set to placeholder value"
    return True, f"{var_name} is set"


def run_preflight_checks() -> Dict[str, List[Tuple[str, str, str]]]:
    """Run all preflight checks and return results."""
    results = {
        "environment": [],
        "dependencies": [],
        "backend": [],
        "frontend": [],
        "database": [],
        "configuration": [],
    }

    # === Environment Checks ===
    python_version = sys.version_info
    if python_version >= (3, 12):
        results["environment"].append(("PASS", "Python version", f"Python {python_version.major}.{python_version.minor}.{python_version.micro}"))
    else:
        results["environment"].append(("FAIL", "Python version", f"Python {python_version.major}.{python_version.minor} (requires 3.12+)"))

    # Check UV
    if check_command_exists("uv"):
        results["environment"].append(("PASS", "UV package manager", "uv is installed"))
    else:
        results["environment"].append(("FAIL", "UV package manager", "uv is not installed"))

    # Check Node.js
    if check_command_exists("node"):
        try:
            result = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True)
            results["environment"].append(("PASS", "Node.js", result.stdout.strip()))
        except subprocess.CalledProcessError:
            results["environment"].append(("FAIL", "Node.js", "node command failed"))
    else:
        results["environment"].append(("FAIL", "Node.js", "node is not installed"))

    # Check Docker (optional)
    if check_command_exists("docker"):
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True, check=True)
            results["environment"].append(("PASS", "Docker", result.stdout.strip()))
        except subprocess.CalledProcessError:
            results["environment"].append(("WARN", "Docker", "docker command failed"))
    else:
        results["environment"].append(("WARN", "Docker", "docker is not installed (optional for embedded DB)"))

    # === Dependency Checks ===
    required_files = [
        "backend/pyproject.toml",
        "frontend/package.json",
        "shared/pyproject.toml",
        "security-agents/pyproject.toml",
        "code-intelligence/pyproject.toml",
        "code-review/pyproject.toml",
        "rl-defense/pyproject.toml",
        "examples/payments-lite/README.md",
    ]

    for file_path in required_files:
        if check_file_exists(file_path):
            results["dependencies"].append(("PASS", f"File exists: {file_path}", "Found"))
        else:
            results["dependencies"].append(("FAIL", f"File exists: {file_path}", "Missing"))

    # Check uv.lock
    if check_file_exists("uv.lock"):
        results["dependencies"].append(("PASS", "uv.lock", "Found"))
    else:
        results["dependencies"].append(("WARN", "uv.lock", "Not found (run `uv sync`)"))

    # === Backend Checks ===
    # Check if backend can be imported
    try:
        subprocess.run(
            ["uv", "run", "python", "-c", "import backend.backend; print('OK')"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        results["backend"].append(("PASS", "Backend import", "backend.backend imports successfully"))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        results["backend"].append(("FAIL", "Backend import", f"Import failed: {e.stderr if e.stderr else str(e)}"))

    # Check if API endpoint is reachable (if running)
    if check_url_reachable("http://localhost:8000/healthz"):
        results["backend"].append(("PASS", "Backend API health", "http://localhost:8000/healthz is reachable"))
    else:
        results["backend"].append(("WARN", "Backend API health", "Backend not running or not reachable"))

    # === Frontend Checks ===
    # Check if frontend can build
    try:
        subprocess.run(
            ["npm", "run", "build"],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd="frontend",
        )
        results["frontend"].append(("PASS", "Frontend build", "Frontend builds successfully"))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        results["frontend"].append(("FAIL", "Frontend build", f"Build failed: {e.stderr[:200] if e.stderr else str(e)}"))

    # Check if frontend is reachable (if running)
    if check_url_reachable("http://localhost:3000"):
        results["frontend"].append(("PASS", "Frontend server", "http://localhost:3000 is reachable"))
    else:
        results["frontend"].append(("WARN", "Frontend server", "Frontend not running or not reachable"))

    # === Database Checks ===
    # Check if .env.example exists
    if check_file_exists(".env.example"):
        results["database"].append(("PASS", ".env.example", "Found"))
    else:
        results["database"].append(("FAIL", ".env.example", "Missing"))

    # Check .env
    if check_file_exists(".env"):
        results["database"].append(("PASS", ".env", "Found"))
    else:
        results["database"].append(("WARN", ".env", "Not found (copy from .env.example)"))

    # Check database URL configuration
    db_url_ok, db_msg = check_environment_variable("DATABASE_URL", required=False)
    results["database"].append((db_url_ok and "PASS" or "WARN", "DATABASE_URL", db_msg))

    # === Configuration Checks ===
    # Check ANTHROPIC_API_KEY (optional for demo, but recommended)
    api_key_ok, api_msg = check_environment_variable("ANTHROPIC_API_KEY", required=False)
    results["configuration"].append((api_key_ok and "PASS" or "WARN", "ANTHROPIC_API_KEY", api_msg))

    # Check GITHUB_WEBHOOK_SECRET
    webhook_ok, webhook_msg = check_environment_variable("GITHUB_WEBHOOK_SECRET", required=False)
    results["configuration"].append((webhook_ok and "PASS" or "WARN", "GITHUB_WEBHOOK_SECRET", webhook_msg))

    # Check SESSION_SECRET
    session_ok, session_msg = check_environment_variable("SESSION_SECRET", required=False)
    results["configuration"].append((session_ok and "PASS" or "WARN", "SESSION_SECRET", session_msg))

    # Check Makefile
    if check_file_exists("Makefile"):
        results["configuration"].append(("PASS", "Makefile", "Found"))
    else:
        results["configuration"].append(("FAIL", "Makefile", "Missing"))

    # Check docker-compose.yml
    if check_file_exists("docker-compose.yml"):
        results["configuration"].append(("PASS", "docker-compose.yml", "Found"))
    else:
        results["configuration"].append(("WARN", "docker-compose.yml", "Missing"))

    return results


def print_summary(results: Dict[str, List[Tuple[str, str, str]]]) -> None:
    """Print a summary of all checks."""
    print(f"\n{BOLD}=== DEMO PREFLIGHT CHECK SUMMARY ==={RESET}\n")

    total = 0
    passed = 0
    failed = 0
    warned = 0

    for category, checks in results.items():
        print(f"{BOLD}{category.upper()}:{RESET}")
        for status, name, message in checks:
            print_status(status, f"{name}: {message}")
            total += 1
            if status == "PASS":
                passed += 1
            elif status == "FAIL":
                failed += 1
            elif status == "WARN":
                warned += 1
        print()

    print(f"{BOLD}OVERALL:{RESET}")
    print(f"Total checks: {total}")
    print(f"{GREEN}Passed: {passed}{RESET}")
    print(f"{RED}Failed: {failed}{RESET}")
    print(f"{YELLOW}Warnings: {warned}{RESET}")
    print()

    if failed == 0:
        print(f"{GREEN}{BOLD}✓ READY FOR DEMO{RESET}")
        return 0
    elif failed > 0:
        print(f"{RED}{BOLD}✗ NOT READY FOR DEMO (fix failed checks){RESET}")
        return 1
    else:
        print(f"{YELLOW}{BOLD}⚠ READY FOR DEMO WITH LIMITATIONS (review warnings){RESET}")
        return 0


def main() -> int:
    """Main entry point."""
    print(f"{BOLD}Demo Preflight Checker{RESET}")
    print("Checking demonstration environment readiness...\n")

    results = run_preflight_checks()
    return print_summary(results)


if __name__ == "__main__":
    sys.exit(main())
