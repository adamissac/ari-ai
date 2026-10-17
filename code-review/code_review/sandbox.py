"""Local-process test runner implementing ``SandboxPort``.

Isolation level is reported honestly as ``local-process``: the command is fixed (pytest
only, never model-authored), runs in a throwaway workspace copy with a scrubbed
environment (no API keys, no tokens), its own process group, CPU/file-size rlimits, a
wall-clock timeout and an output cap. It does NOT enforce network isolation; production
runs use the shared Docker sandbox driver from ``security_agents`` through the same port.
"""

from __future__ import annotations

import json
import os
import re
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

from code_review.ports import CaseResult, ExecResult

_PLUGIN_SRC = Path(__file__).with_name("_pytest_report.py")
_TARGET = re.compile(r"^[A-Za-z0-9_./\-]+(::[A-Za-z0-9_\[\]\-.]+)*$")
OUTPUT_CAP = 200_000


class SandboxPolicyError(Exception):
    pass


def validate_targets(targets: Sequence[str]) -> list[str]:
    out = []
    for t in targets:
        if t.startswith("-") or ".." in t or t.startswith("/") or not _TARGET.match(t):
            raise SandboxPolicyError(f"refusing pytest target {t!r}")
        out.append(t)
    return out


def _limits(cpu_s: int) -> None:  # runs in the child before exec
    os.setsid()
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))


class LocalProcessSandbox:
    name = "local-process"
    isolation_level = "local-process (scrubbed env, rlimits, timeout; no network isolation)"

    def __init__(self, python: str | None = None) -> None:
        self.python = python or os.environ.get("CODE_REVIEW_SANDBOX_PYTHON") or sys.executable

    def run_pytest(
        self, project_dir: Path, targets: Sequence[str], *, timeout_s: float
    ) -> ExecResult:
        safe = validate_targets(targets)
        with tempfile.TemporaryDirectory(prefix="cr-sbx-") as scratch:
            sdir = Path(scratch)
            shutil.copy(_PLUGIN_SRC, sdir / "cr_pytest_report.py")
            report = sdir / "report.json"
            env = {
                "PATH": "/usr/bin:/bin",
                "HOME": str(sdir),
                "PYTHONPATH": f"{sdir}{os.pathsep}{project_dir}",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
                "CR_REPORT_PATH": str(report),
                "LANG": "C.UTF-8",
            }
            cmd = [
                self.python,
                "-m",
                "pytest",
                "-q",
                "-p",
                "cr_pytest_report",
                "-p",
                "no:cacheprovider",
                "--rootdir",
                str(project_dir),
                *safe,
            ]
            started = time.monotonic()
            proc = subprocess.Popen(
                cmd,
                cwd=project_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=lambda: _limits(int(timeout_s) + 5),
            )
            timed_out = False
            try:
                out, err = proc.communicate(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(proc.pid, signal.SIGKILL)
                out, err = proc.communicate()
            duration = time.monotonic() - started
            cases: list[CaseResult] = []
            if report.exists():
                data = json.loads(report.read_text())
                cases = [CaseResult(**c) for c in data.get("cases", [])]
        display = ["python", *("<project>" if c == str(project_dir) else c for c in cmd[1:])]
        return ExecResult(
            command=display,
            exit_code=None if timed_out else proc.returncode,
            stdout=out.decode(errors="replace")[-OUTPUT_CAP:],
            stderr=err.decode(errors="replace")[-OUTPUT_CAP:],
            duration_s=duration,
            timed_out=timed_out,
            cases=cases,
            driver=self.name,
            isolation_level=self.isolation_level,
        )


BEHAVIORAL_EXC = {"AssertionError", "Failed"}


def classify(result: ExecResult) -> str:
    """passed | failed (behavioral assertion) | error (tooling/harness, inconclusive)."""
    if result.timed_out or result.exit_code is None:
        return "error"
    if result.exit_code not in (0, 1):  # 2 interrupted, 3 internal, 4 usage, 5 no tests
        return "error"
    if not result.cases:
        return "error"
    failing = [c for c in result.cases if c.outcome in ("failed", "error")]
    if not failing:
        return "passed" if any(c.outcome == "passed" for c in result.cases) else "error"
    if any(c.outcome == "error" or c.exc_type not in BEHAVIORAL_EXC for c in failing):
        return "error"
    return "failed"
