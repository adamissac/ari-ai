"""``SandboxPort`` over the shared security_agents sandbox drivers (Alan).

MASTER_BUILD_SPEC §10: the reviewer shares the sandbox driver instead of keeping its own
execution path. The command is still fixed (the drivers' ``pytest`` mode, never
model-authored); the reviewer's reporting plugin rides along as an ``extra_files`` entry
in ``.sandbox/`` and writes its JSON to the driver's ``/out``.

Driver selection (``CODE_REVIEW_SANDBOX``), one policy with the security agents
(``security_agents.host_adapter._driver``):

* unset (default)  — ``local`` in development/test; elsewhere the same isolated driver as
                     the seven security agents (``vercel`` when ``SECURITY_SANDBOX=vercel``,
                     else ``docker``);
* ``docker``       — ``DockerSandboxDriver`` (network none, non-root, tmpfs);
* ``vercel``       — ``VercelSandboxDriver`` (deny-all egress microVM);
* ``shared-local`` — ``LocalProcessDriver`` (requires ``SANDBOX_ALLOW_LOCAL_PROCESS=1``);
* ``local``        — ``code_review.sandbox.LocalProcessSandbox``.

``local`` and ``shared-local`` run customer code as a host process: they are refused unless
``APP_ENV`` is development/test (fail closed; no silent fallback to the host).
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
        from security_agents.sandbox.driver import SandboxLimits, SandboxProfile, SandboxSpec  # type: ignore[import-not-found,unused-ignore]

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


_HOST_PROCESS = ("local", "shared-local")


def _environment() -> tuple[str, str]:
    """(APP_ENV, SECURITY_SANDBOX) from the backend settings when hosted, else the env."""
    try:
        from backend.settings import get_settings  # type: ignore[import-not-found,unused-ignore]
    except ImportError:  # standalone reviewer (CLI / tests without the backend package)
        return os.environ.get("APP_ENV", "development"), os.environ.get("SECURITY_SANDBOX", "")
    # Hosted: an invalid backend configuration must surface (fail closed), never be masked
    # by a fallback that could re-allow host-process execution.
    s = get_settings()
    return str(s.app_env), str(s.security_sandbox)


def build_sandbox(kind: str | None = None) -> SandboxPort:
    app_env, security_sandbox = _environment()
    dev = app_env in ("development", "test")
    # Development/test keep the local default; anywhere else the reviewer uses the same
    # isolated driver as the security agents (vercel when configured, else docker).
    default = "local" if dev else ("vercel" if security_sandbox == "vercel" else "docker")
    kind = kind or os.environ.get("CODE_REVIEW_SANDBOX") or default
    if kind in _HOST_PROCESS and not dev:
        from code_review.agent import ReviewError
        from shared.errors import ErrorCode

        raise ReviewError(
            ErrorCode.SANDBOX_POLICY_VIOLATION,
            f"CODE_REVIEW_SANDBOX={kind} runs customer tests as a host process; "
            f"refused outside development/test (APP_ENV={app_env})",
        )
    if kind == "local":
        return LocalProcessSandbox()
    from security_agents.sandbox import driver as d  # type: ignore[import-not-found,unused-ignore]

    if kind == "docker":
        return SharedSandboxAdapter(d.DockerSandboxDriver())
    if kind == "vercel":
        from security_agents.sandbox.vercel_driver import VercelSandboxDriver  # type: ignore[import-not-found,unused-ignore]

        return SharedSandboxAdapter(VercelSandboxDriver())
    if kind == "shared-local":
        return SharedSandboxAdapter(d.LocalProcessDriver())
    raise ValueError(f"unknown CODE_REVIEW_SANDBOX {kind!r}")
