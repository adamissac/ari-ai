"""Vercel Sandbox driver: run the untrusted workspace in a throwaway microVM.

Each run creates a fresh Vercel Sandbox with **deny-all** egress (loopback only), stages
the workspace, and runs the same `.sandbox/entry.py` the other drivers use, so the agents
are unchanged. The microVM is the untrusted boundary: it holds no host credentials and
cannot reach the control plane. The sandbox is always destroyed at the end of the run.

For a served target (`target-only`), the target app is served in-process on 127.0.0.1:8000
inside the same microVM and reached at `SANDBOX_TARGET_URL=http://127.0.0.1:8000`; external
egress stays denied. Credentials come from the environment (`VERCEL_TOKEN`,
`VERCEL_PROJECT_ID`, `VERCEL_TEAM_ID`) and are read by the SDK, never by this module.

The network policy is a hard microVM boundary; `entry.py`'s in-process guard is defence in
depth. Commands are never model-authored (fixed `entry.py` modes).
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from ..contracts import ErrorCode, PlatformError, new_id
from .driver import (
    SandboxResult,
    SandboxSpec,
    _cap,
    _stage_workspace,
    validate_spec,
)

WORKDIR = "/vercel/sandbox/work"
TARGETDIR = "/vercel/sandbox/target"
# The microVM image ships bare Python; Probe/Verify checks need these to run and serve
# ASGI targets. Fixed and pinned: never derived from the repository under test.
PYPI_DOMAINS = ("pypi.org", "files.pythonhosted.org")
UBUNTU_DOMAINS = ("archive.ubuntu.com", "security.ubuntu.com")
APT_HTTPS = (
    "sed -i s,http://,https://,g /etc/apt/sources.list.d/ubuntu.sources && "
    "find /etc/apt/sources.list.d -type f ! -name ubuntu.sources -delete"
)
RUNNER_WHEELS = (
    "pytest==8.4.2",
    "httpx==0.28.1",
    "fastapi==0.143.3",
    "uvicorn==0.54.0",
    "pydantic==2.14.1",
)
OUT_MARKER = "\n@@SANDBOX_OUT@@"


class VercelBox(Protocol):
    """The slice of a Vercel Sandbox this driver uses. A fake implements it in tests."""

    def put_archive(self, tar_bytes: bytes, dest: str) -> None: ...
    def run(
        self, argv: list[str], *, cwd: str, env: dict[str, str], timeout: float
    ) -> tuple[int | None, str, str, bool]: ...
    def start(self, argv: list[str], *, cwd: str, env: dict[str, str]) -> None: ...
    def logs(self) -> str: ...
    def stop(self) -> None: ...


BoxFactory = Callable[[SandboxSpec, str, bool], VercelBox]


def _default_factory(
    spec: SandboxSpec, run_id: str, needs_target: bool
) -> VercelBox:  # pragma: no cover - needs live Vercel
    return _VercelSdkBox(spec, run_id)


class VercelSandboxDriver:
    """Run a sandbox spec in a Vercel Sandbox microVM. Fails closed on policy violations."""

    name = "vercel-sandbox"
    isolation_level = "microvm"

    def __init__(self, *, factory: BoxFactory | None = None) -> None:
        self._factory = factory or _default_factory

    def run(self, spec: SandboxSpec) -> SandboxResult:
        validate_spec(spec)
        run_id = new_id("sbx").lower().replace("_", "-")
        started = datetime.now(UTC)
        needs_target = spec.target_workspace is not None
        if needs_target and spec.target_app is None:
            raise PlatformError(ErrorCode.SANDBOX_POLICY_VIOLATION, "served target needs a target app")
        root = Path(tempfile.mkdtemp(prefix=f"{run_id}-"))
        box: VercelBox | None = None
        target_log = ""
        t0 = time.monotonic()
        try:
            ws = _stage_workspace(spec, root)
            ws_tar = _tar(ws)
            box = self._factory(spec, run_id, needs_target)
            box.put_archive(ws_tar, WORKDIR)

            env = {
                "SANDBOX_OUT": "/tmp/out",
                "SANDBOX_NETWORK": "none" if spec.network == "none" else "target-only",
                "SANDBOX_EMIT_OUT": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            if needs_target:
                box.put_archive(_tar_target(spec), TARGETDIR)
                box.start(
                    [
                        "python",
                        "-m",
                        "uvicorn",
                        "--factory",
                        str(spec.target_app),
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8000",
                    ],
                    cwd=TARGETDIR,
                    env={"PYTHONDONTWRITEBYTECODE": "1"},
                )
                _await_ready(box)
                env["SANDBOX_TARGET_URL"] = "http://127.0.0.1:8000"

            exit_code, stdout, stderr, timed_out = box.run(
                ["python", "-I", "-B", ".sandbox/entry.py", spec.mode, *spec.args],
                cwd=WORKDIR,
                env=env,
                timeout=spec.limits.timeout_s,
            )
            if needs_target:
                target_log = _cap(box.logs())
            out_files, stdout = _split_out(stdout)
            return SandboxResult(
                run_id=run_id,
                driver=self.name,
                isolation_level=self.isolation_level,
                profile=spec.profile.value,
                network=spec.network,
                exit_code=None if timed_out else exit_code,
                stdout=_cap(stdout),
                stderr=_cap(stderr),
                out_files=out_files,
                duration_s=time.monotonic() - t0,
                timed_out=timed_out,
                started_at=started,
                labels=dict(spec.labels),
                target_log=target_log,
            )
        finally:
            if box is not None:
                with _suppress():
                    box.stop()
            _rmtree(root)


# macOS tar otherwise adds AppleDouble `._*` files, which Python then fails to import.
_TAR_ENV = {**os.environ, "COPYFILE_DISABLE": "1"}


def _tar(ws: Path) -> bytes:
    return subprocess.run(
        ["tar", "-c", "-C", str(ws), "."], capture_output=True, check=True, env=_TAR_ENV
    ).stdout


def _tar_target(spec: SandboxSpec) -> bytes:
    assert spec.target_workspace is not None
    return subprocess.run(
        ["tar", "-c", "-C", str(spec.target_workspace), "--exclude", ".sandbox", "."],
        capture_output=True,
        check=True,
        env=_TAR_ENV,
    ).stdout


def _await_ready(box: VercelBox, attempts: int = 40) -> None:
    for _ in range(attempts):
        code, _out, _err, _timed = box.run(
            [
                "python",
                "-c",
                "import socket,sys; s=socket.create_connection(('127.0.0.1',8000),1); s.close()",
            ],
            cwd=WORKDIR,
            env={},
            timeout=5,
        )
        if code == 0:
            return
        time.sleep(0.5)
    raise PlatformError(ErrorCode.SANDBOX_START_FAILED, "served target did not become ready")


def _split_out(stdout: str) -> tuple[dict[str, bytes], str]:
    if OUT_MARKER not in stdout:
        return {}, stdout
    body, payload = stdout.rsplit(OUT_MARKER, 1)
    try:
        return {k: base64.b64decode(v) for k, v in json.loads(payload).items()}, body
    except (ValueError, json.JSONDecodeError):
        return {}, body


class _suppress:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> bool:
        return True


def _rmtree(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)


class _VercelSdkBox:  # pragma: no cover - requires live Vercel credentials
    """Real Vercel Sandbox, created with deny-all egress. Destroyed by `stop()`.

    Named sandboxes snapshot on stop; without destroy those snapshots leak and exhaust
    the account's snapshot storage (HTTP 402), so `stop()` destroys them too."""

    def __init__(self, spec: SandboxSpec, run_id: str) -> None:
        from vercel.sandbox import NetworkPolicy
        from vercel.sandbox import sync as vsandbox

        # Egress reaches only PyPI (and the Ubuntu mirrors when the recipe needs system
        # packages) while fixed runner wheels and the recipe's pinned packages install; it is
        # deny-all before any repository code is staged or run.
        domains = PYPI_DOMAINS + (UBUNTU_DOMAINS if spec.apt else ())
        self._box = vsandbox.create_sandbox(
            name=f"ari-{run_id}",
            execution_time_limit=int(spec.limits.timeout_s) + 240,
            network_policy=NetworkPolicy.custom(dict.fromkeys(domains, ())),
            tags={k[:63]: v[:200] for k, v in spec.labels.items()},
            persistent=False,
            destroy=False,
        )
        try:  # the driver stops only boxes it received, so a failed boot destroys itself
            try:
                if spec.apt:
                    env = {"DEBIAN_FRONTEND": "noninteractive"}
                    # The egress allowlist passes TLS only: use the HTTPS Ubuntu mirrors and
                    # drop third-party lists (e.g. cli.github.com) that are not allowed.
                    self._box.run_process("sh", ["-c", APT_HTTPS], sudo=True, check=True, capture_output=True)
                    self._box.run_process(
                        "apt-get", ["update", "-qq"], sudo=True, env=env, check=True, capture_output=True
                    )
                    self._box.run_process(
                        "apt-get",
                        ["install", "-y", "-qq", "--no-install-recommends", *spec.apt],
                        sudo=True,
                        env=env,
                        check=True,
                        capture_output=True,
                    )
                self._box.run_process(
                    "python",
                    [
                        "-m",
                        "pip",
                        "install",
                        "-q",
                        "--root-user-action=ignore",
                        "--only-binary=:all:",
                        *RUNNER_WHEELS,
                        *spec.pip,
                    ],
                    sudo=True,  # system site-packages: the entry runs `python -I`, which skips user site
                    check=True,
                    capture_output=True,
                )
            finally:
                self._box.update_network_policy(NetworkPolicy.deny_all())
            for d in (WORKDIR, TARGETDIR, "/tmp/out"):
                self._box.fs.mkdir(d, recursive=True)
        except BaseException:
            self.stop()
            raise

    def put_archive(self, tar_bytes: bytes, dest: str) -> None:
        self._box.fs.write_bytes("/tmp/stage.tar", tar_bytes)
        self._box.run_process("tar", ["-xf", "/tmp/stage.tar", "-C", dest], check=True)

    def run(
        self, argv: list[str], *, cwd: str, env: dict[str, str], timeout: float
    ) -> tuple[int | None, str, str, bool]:
        from vercel.sandbox import SandboxTimeoutError

        try:
            cp = self._box.run_process(
                argv[0], argv[1:], cwd=cwd, env=env, kill_after=timeout, capture_output=True
            )
        except SandboxTimeoutError:
            return None, "", "timeout", True
        return cp.returncode, cp.stdout or "", cp.stderr or "", False

    def start(self, argv: list[str], *, cwd: str, env: dict[str, str]) -> None:
        self._box.create_process(argv[0], argv[1:], cwd=cwd, env=env)

    def logs(self) -> str:
        return ""

    def stop(self) -> None:
        try:
            self._box.stop()
        finally:
            self._box.destroy(delete_orphan_snapshots=True)
