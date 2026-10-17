"""Shared execution/reporting for the QA entry points; no dependency installation."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Result:
    name: str
    status: str
    detail: str = ""

    def __post_init__(self) -> None:
        if self.status not in {"PASS", "FAIL", "SKIP"}:
            raise ValueError("Unknown QA status")


def exit_code(results: list[Result]) -> int:
    if any(r.status == "FAIL" for r in results):
        return 1
    return 2 if any(r.status == "SKIP" for r in results) else 0


def report(results: list[Result]) -> int:
    for result in results:
        print(f"{result.status}: {result.name}{' — ' + result.detail if result.detail else ''}")
    code = exit_code(results)
    print(
        {
            0: "Selected checks passed.",
            1: "Selected checks failed.",
            2: "Checks incomplete; skipped checks are not passes.",
        }[code]
    )
    return code


def run(
    name: str,
    command: list[str],
    *,
    cwd: Path = ROOT,
    timeout: int = 900,
    incomplete_exit: bool = False,
) -> Result:
    env = dict(os.environ, RUN_LIVE_LLM_EVAL="0")
    print(f"Running {name}", flush=True)
    try:
        completed = subprocess.run(command, cwd=cwd, env=env, timeout=timeout, check=False)
    except FileNotFoundError:
        return Result(name, "SKIP", f"Required executable unavailable: {command[0]}")
    except subprocess.TimeoutExpired:
        return Result(name, "FAIL", f"Timed out after {timeout}s")
    status = (
        "PASS"
        if completed.returncode == 0
        else "SKIP"
        if incomplete_exit and completed.returncode == 2
        else "FAIL"
    )
    return Result(name, status, f"exit {completed.returncode}")


def pytest(name: str, *paths: str) -> Result:
    return run(name, [sys.executable, "-m", "pytest", *paths, "-q", "-ra"])
