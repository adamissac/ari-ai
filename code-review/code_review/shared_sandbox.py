"""``SandboxPort`` over the shared security_agents sandbox drivers (Alan).

MASTER_BUILD_SPEC §10: the reviewer shares the sandbox driver instead of keeping its own
execution path. The command is still fixed (the drivers' ``pytest`` mode, never
model-authored); the reviewer's reporting plugin rides along as an ``extra_files`` entry
in ``.sandbox/`` and writes its JSON to the driver's ``/out``.

Driver selection (``CODE_REVIEW_SANDBOX``):

* ``docker``          — ``DockerSandboxDriver`` (network none, non-root, tmpfs; the default
                        outside dev/test once images are pinned — INFRA-005);
* ``shared-local``    — ``LocalProcessDriver`` (dev only; requires
                        ``SANDBOX_ALLOW_LOCAL_PROCESS=1``; not a security boundary);
* ``local`` (default) — ``code_review.sandbox.LocalProcessSandbox``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from code_review.ports import CaseResult, ExecResult, SandboxPort
from code_review.sandbox import LocalProcessSandbox, validate_targets

_PLUGIN = Path(__file__).with_name("_pytest_report.py")
REPORT_NAME = "cr_report.json"


class SharedSandboxAdapter:
    def __init__(self, driver: Any) -> None:
        self.driver = driver
        self.name = f"security_agents:{driver.name}"
        self.isolation_level = str(driver.isolation_level)

    def run_pytest(
        self, project_dir: Path, targets: Sequence[str], *, timeout_s: float
    ) -> ExecResult:
        from security_agents.sandbox.driver import SandboxLimits, SandboxProfile, SandboxSpec

        args = ["-q", "-p", "cr_pytest_report", *validate_targets(targets)]
        spec = SandboxSpec(
            profile=SandboxProfile.TEST_RUNNER,
            network="none",
            workspace=project_dir,
            mode="pytest",
            args=args,
            labels={"component": "code_review"},
            limits=SandboxLimits(timeout_s=timeout_s),
            extra_files={"cr_pytest_report.py": _PLUGIN.read_text(encoding="utf-8")},
        )
        r = self.driver.run(spec)
        cases: list[CaseResult] = []
        raw = r.out_files.get(REPORT_NAME)
        if raw:
            cases = [CaseResult(**c) for c in json.loads(raw.decode("utf-8")).get("cases", [])]
        return ExecResult(
            command=["python", "-I", "-B", ".sandbox/entry.py", "pytest", *args],
            exit_code=r.exit_code,
            stdout=r.stdout,
            stderr=r.stderr,
            duration_s=r.duration_s,
            timed_out=r.timed_out,
            cases=cases,
            driver=f"{self.name}#{r.run_id}",
            isolation_level=r.isolation_level,
        )


def build_sandbox(kind: str | None = None) -> SandboxPort:
    kind = kind or os.environ.get("CODE_REVIEW_SANDBOX", "local")
    if kind == "local":
        return LocalProcessSandbox()
    from security_agents.sandbox import driver as d

    if kind == "docker":
        return SharedSandboxAdapter(d.DockerSandboxDriver())
    if kind == "shared-local":
        return SharedSandboxAdapter(d.LocalProcessDriver())
    raise ValueError(f"unknown CODE_REVIEW_SANDBOX {kind!r}")
