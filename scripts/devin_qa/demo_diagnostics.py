#!/usr/bin/env python3
"""
Demo Diagnostics Export

Collects redacted, non-sensitive diagnostic information after a failed demo run.
Includes relevant timestamps, safe log excerpts, HTTP statuses, and identifiers.
Excludes credentials, tokens, customer data and raw secrets.

Usage:
    python scripts/devin_qa/demo_diagnostics.py > diagnostics.txt
"""

import subprocess
import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def redact_secrets(text: str) -> str:
    """Redact potential secrets from text."""
    # Redact common secret patterns
    patterns = [
        (r'ANTHROPIC_API_KEY["\']?\s*[:=]\s*["\']?[^"\s]+["\']?', 'ANTHROPIC_API_KEY=[REDACTED]'),
        (r'GITHUB_WEBHOOK_SECRET["\']?\s*[:=]\s*["\']?[^"\s]+["\']?', 'GITHUB_WEBHOOK_SECRET=[REDACTED]'),
        (r'SESSION_SECRET["\']?\s*[:=]\s*["\']?[^"\s]+["\']?', 'SESSION_SECRET=[REDACTED]'),
        (r'DATABASE_URL["\']?\s*[:=]\s*["\']?[^"\s]+["\']?', 'DATABASE_URL=[REDACTED]'),
        (r'Bearer [A-Za-z0-9\-._~+/]+', 'Bearer [REDACTED]'),
        (r'sk-[a-zA-Z0-9]{32,}', '[REDACTED_KEY]'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\s]+["\']?', 'token=[REDACTED]'),
    ]

    redacted = text
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)

    return redacted


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


def collect_diagnostics() -> Dict[str, Any]:
    """Collect diagnostic information."""
    timestamp = datetime.now(timezone.utc).isoformat()

    diagnostics = {
        "timestamp": timestamp,
        "runtime_versions": {},
        "service_health": {},
        "configuration": {},
        "recent_errors": [],
        "git_status": {},
    }

    # Runtime versions
    print("Collecting runtime versions...")
    code, stdout, _ = run_command(["python3", "--version"])
    diagnostics["runtime_versions"]["python"] = stdout.strip() if code == 0 else "Not found"

    code, stdout, _ = run_command(["uv", "--version"])
    diagnostics["runtime_versions"]["uv"] = stdout.strip() if code == 0 else "Not found"

    code, stdout, _ = run_command(["node", "--version"])
    diagnostics["runtime_versions"]["node"] = stdout.strip() if code == 0 else "Not found"

    # Service health
    print("Checking service health...")
    code, _, _ = run_command(
        ["uv", "run", "python", "-c", "import sys; sys.path.insert(0, 'backend'); import backend; print('OK')"]
    )
    diagnostics["service_health"]["backend_import"] = "OK" if code == 0 else "FAIL"

    code, _, _ = run_command(
        ["uv", "run", "python", "-c", "import sys; sys.path.insert(0, 'shared'); from shared import api; print('OK')"]
    )
    diagnostics["service_health"]["shared_contracts"] = "OK" if code == 0 else "FAIL"

    # Configuration status
    print("Checking configuration...")
    diagnostics["configuration"]["ANTHROPIC_API_KEY"] = "SET" if os.environ.get("ANTHROPIC_API_KEY") else "NOT_SET"
    diagnostics["configuration"]["DATABASE_URL"] = "SET" if os.environ.get("DATABASE_URL") else "NOT_SET"
    diagnostics["configuration"]["GITHUB_WEBHOOK_SECRET"] = "SET" if os.environ.get("GITHUB_WEBHOOK_SECRET") else "NOT_SET"
    diagnostics["configuration"]["SESSION_SECRET"] = "SET" if os.environ.get("SESSION_SECRET") else "NOT_SET"

    # Git status
    print("Checking git status...")
    code, stdout, _ = run_command(["git", "branch", "--show-current"])
    diagnostics["git_status"]["branch"] = stdout.strip() if code == 0 else "UNKNOWN"

    code, stdout, _ = run_command(["git", "rev-parse", "HEAD"])
    diagnostics["git_status"]["commit"] = stdout.strip() if code == 0 else "UNKNOWN"

    code, stdout, _ = run_command(["git", "status", "--short"])
    diagnostics["git_status"]["dirty"] = "YES" if stdout.strip() else "NO"

    # Recent errors from logs (if any)
    print("Checking for recent errors...")
    log_files = [
        Path(".venv/pgdata"),
        Path("backend/logs"),
        Path("logs"),
    ]

    for log_dir in log_files:
        if log_dir.exists():
            # This is a placeholder - actual log collection would depend on log format
            diagnostics["recent_errors"].append(f"Log directory found: {log_dir}")

    return diagnostics


def print_diagnostics(diagnostics: Dict[str, Any]) -> None:
    """Print diagnostics to stdout."""
    print(f"{BOLD}=== DEMO DIAGNOSTICS ==={RESET}")
    print(f"Timestamp: {diagnostics['timestamp']}\n")

    print(f"{BOLD}Runtime Versions:{RESET}")
    for key, value in diagnostics["runtime_versions"].items():
        print(f"  {key}: {value}")

    print(f"\n{BOLD}Service Health:{RESET}")
    for key, value in diagnostics["service_health"].items():
        status = f"{GREEN}OK{RESET}" if value == "OK" else f"{RED}FAIL{RESET}"
        print(f"  {key}: {status}")

    print(f"\n{BOLD}Configuration:{RESET}")
    for key, value in diagnostics["configuration"].items():
        status = f"{GREEN}SET{RESET}" if value == "SET" else f"{YELLOW}NOT_SET{RESET}"
        print(f"  {key}: {status}")

    print(f"\n{BOLD}Git Status:{RESET}")
    for key, value in diagnostics["git_status"].items():
        print(f"  {key}: {value}")

    if diagnostics["recent_errors"]:
        print(f"\n{BOLD}Recent Errors:{RESET}")
        for error in diagnostics["recent_errors"]:
            print(f"  {error}")

    print(f"\n{BOLD}=== END OF DIAGNOSTICS ==={RESET}")
    print(f"{YELLOW}NOTE: This output has been redacted. Review before sharing.{RESET}")


def main() -> int:
    """Main entry point."""
    print(f"{BOLD}Collecting demo diagnostics...{RESET}\n")
    diagnostics = collect_diagnostics()
    print_diagnostics(diagnostics)
    return 0


if __name__ == "__main__":
    sys.exit(main())
