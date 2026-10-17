"""Sandbox driver: profiles, network modes, limits, local-dev and Docker drivers.

Commands are never model-authored: callers choose one of the fixed modes in
`entry.py` and pass typed arguments. The driver re-checks the scope decision
before attaching any target network (docs/15 §3(c)).
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol

from ..contracts import ErrorCode, PlatformError, new_id
from ..redact import redact_text
from ..scope_guard import Decision
from .workspace import copy_tree

ENTRY_SRC = Path(__file__).with_name("entry.py")
HARNESS_SRC = Path(__file__).parent.parent / "checks" / "harness.py"


class SandboxProfile(StrEnum):
    TEST_RUNNER = "test-runner"
    CHECK_RUNNER = "check-runner"
    TARGET = "target"


NetworkMode = Literal["none", "target-only"]

PROFILE_NETWORK: dict[SandboxProfile, frozenset[str]] = {
    SandboxProfile.TEST_RUNNER: frozenset({"none"}),
    SandboxProfile.CHECK_RUNNER: frozenset({"target-only"}),
    SandboxProfile.TARGET: frozenset({"target-only"}),
}


@dataclass(frozen=True)
class SandboxLimits:
    cpus: float = 1.0
    memory_mb: int = int(os.environ.get("SANDBOX_MAX_MEMORY_MB", "2048"))
    pids: int = 256
    timeout_s: float = float(os.environ.get("SANDBOX_DEFAULT_TIMEOUT_SECONDS", "300"))
    output_bytes: int = 50 * 1024 * 1024


@dataclass(frozen=True)
class SandboxSpec:
    profile: SandboxProfile
    network: NetworkMode
    workspace: Path  # host dir copied *into* the sandbox (never mounted)
    mode: Literal["pytest", "check", "netprobe"]
    args: list[str]
    labels: dict[str, str]
    limits: SandboxLimits = field(default_factory=SandboxLimits)
    extra_files: dict[str, str] = field(default_factory=dict)  # name -> content, placed in .sandbox/
    target_id: str | None = None
    scope_decision: Decision | None = None  # must be an allowed attach_network decision for target-only


@dataclass
class SandboxResult:
    run_id: str
    driver: str
    isolation_level: str
    profile: str
    network: str
    exit_code: int | None
    stdout: str
    stderr: str
    out_files: dict[str, bytes]
    duration_s: float
    timed_out: bool
    started_at: datetime
    labels: dict[str, str]

    def out_json(self, name: str) -> dict[str, object] | None:
        data = self.out_files.get(name)
        if data is None:
            return None
        try:
            parsed = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None


class SandboxDriver(Protocol):
    name: str
    isolation_level: str

    def run(self, spec: SandboxSpec) -> SandboxResult: ...


FORBIDDEN_WORKSPACE_ROOTS = (
    Path("/"),
    Path("/Users"),
    Path("/home"),
    Path("/etc"),
    Path("/var"),
    Path.home(),
)


def validate_spec(spec: SandboxSpec) -> None:
    """Policy checks shared by every driver. Fails closed."""
    workspace = spec.workspace.resolve()
    if workspace in (p.resolve() for p in FORBIDDEN_WORKSPACE_ROOTS) or len(workspace.parts) <= 2:
        raise PlatformError(
            ErrorCode.SANDBOX_POLICY_VIOLATION,
            f"refusing to stage {workspace} as a sandbox workspace",
        )
    if not workspace.is_dir():
        raise PlatformError(ErrorCode.SANDBOX_START_FAILED, f"workspace {workspace} is not a directory")
    if spec.network not in PROFILE_NETWORK[spec.profile]:
        raise PlatformError(
            ErrorCode.SANDBOX_POLICY_VIOLATION,
            f"profile {spec.profile.value} does not permit network {spec.network}",
        )
    if spec.network == "target-only":
        d = spec.scope_decision
        if d is None or not d.allowed or spec.target_id is None:
            raise PlatformError(
                ErrorCode.SCOPE_DENIED, "target-only network requires an allowed scope decision"
            )
    for name in spec.extra_files:
        if "/" in name or name.startswith(".") or name in ("entry.py", "harness.py"):
            raise PlatformError(ErrorCode.SANDBOX_POLICY_VIOLATION, f"bad extra file name {name!r}")
    for k, v in spec.labels.items():
        if not k.replace("_", "").replace(".", "").isalnum() or len(v) > 200:
            raise PlatformError(ErrorCode.SANDBOX_POLICY_VIOLATION, "bad label")


def _stage_workspace(spec: SandboxSpec, root: Path) -> Path:
    ws = root / "ws"
    copy_tree(spec.workspace, ws)
    sb = ws / ".sandbox"
    sb.mkdir()
    shutil.copy2(ENTRY_SRC, sb / "entry.py")
    if HARNESS_SRC.is_file():  # reviewed check harness is installed separately (security-owner authored)
        shutil.copy2(HARNESS_SRC, sb / "harness.py")
    for name, content in spec.extra_files.items():
        (sb / name).write_text(content, encoding="utf-8")
    return ws


def _cap(text: str, limit: int = 200_000) -> str:
    text = redact_text(text)
    return text if len(text) <= limit else text[:limit] + "\n[truncated]"


# --------------------------------------------------------------------------- local dev driver


class LocalProcessDriver:
    """DEV-ONLY driver: subprocess with scrubbed env, copy-in workspace, rlimits,
    process-group kill on timeout and a Python-level network guard.

    This is NOT a security boundary (shared kernel, same user, no filesystem
    isolation beyond a temp copy). It exists so the owned `examples/` fixtures
    can be exercised on laptops without Docker. It refuses to construct unless
    `SANDBOX_ALLOW_LOCAL_PROCESS=1` (or `allow=True` in tests), and every result
    is labelled with its isolation level.
    """

    name = "local-process"
    isolation_level = "process-dev:not-a-security-boundary"

    def __init__(self, *, python: str | None = None, allow: bool | None = None) -> None:
        allowed = allow if allow is not None else os.environ.get("SANDBOX_ALLOW_LOCAL_PROCESS") == "1"
        if not allowed:
            raise PlatformError(
                ErrorCode.SANDBOX_START_FAILED,
                "local-process driver disabled; set SANDBOX_ALLOW_LOCAL_PROCESS=1 for owned fixtures only",
            )
        self.python = python or sys.executable

    def run(self, spec: SandboxSpec) -> SandboxResult:
        validate_spec(spec)
        run_id = new_id("sbx")
        started = datetime.now(UTC)
        root = Path(tempfile.mkdtemp(prefix=f"{run_id}-"))
        try:
            ws = _stage_workspace(spec, root)
            out = root / "out"
            out.mkdir()
            home = root / "home"
            home.mkdir()
            tmp = root / "tmp"
            tmp.mkdir()
            for p in ws.rglob("*"):
                if p.is_file():
                    p.chmod(0o444)
            network = "target-inprocess" if spec.network == "target-only" else "none"
            env = {
                "PATH": "/usr/bin:/bin",
                "HOME": str(home),
                "TMPDIR": str(tmp),
                "SANDBOX_OUT": str(out),
                "SANDBOX_NETWORK": network,
                "PYTHONHASHSEED": "0",
                "PYTHONDONTWRITEBYTECODE": "1",
                "LANG": "C.UTF-8",
            }
            argv = [self.python, "-I", "-B", str(ws / ".sandbox" / "entry.py"), spec.mode, *spec.args]
            limits = spec.limits

            def _preexec() -> None:  # runs in the child
                cpu = int(limits.timeout_s) + 5
                resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
                resource.setrlimit(resource.RLIMIT_FSIZE, (limits.output_bytes, limits.output_bytes))
                resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))

            t0 = time.monotonic()
            proc = subprocess.Popen(
                argv,
                cwd=ws,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                preexec_fn=_preexec,
            )
            timed_out = False
            try:
                stdout_b, stderr_b = proc.communicate(timeout=limits.timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(proc.pid, signal.SIGKILL)
                stdout_b, stderr_b = proc.communicate()
            duration = time.monotonic() - t0
            out_files: dict[str, bytes] = {}
            total = 0
            for p in sorted(out.iterdir()):
                if p.is_file():
                    data = p.read_bytes()
                    total += len(data)
                    if total > limits.output_bytes:
                        break
                    out_files[p.name] = data
            return SandboxResult(
                run_id=run_id,
                driver=self.name,
                isolation_level=self.isolation_level,
                profile=spec.profile.value,
                network=spec.network,
                exit_code=None if timed_out else proc.returncode,
                stdout=_cap(stdout_b.decode("utf-8", "replace")),
                stderr=_cap(stderr_b.decode("utf-8", "replace")),
                out_files=out_files,
                duration_s=duration,
                timed_out=timed_out,
                started_at=started,
                labels=dict(spec.labels),
            )
        finally:
            for p in root.rglob("*"):
                with contextlib.suppress(OSError):
                    p.chmod(0o755 if p.is_dir() else 0o644)
            shutil.rmtree(root, ignore_errors=True)


# --------------------------------------------------------------------------- docker driver

CommandRunner = Callable[[list[str], bytes | None, float], subprocess.CompletedProcess[bytes]]


def _default_runner(
    argv: list[str], stdin: bytes | None, timeout: float
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(argv, input=stdin, capture_output=True, timeout=timeout, check=False)


LABEL_ROOT = "hackatl.sandbox"


class DockerSandboxDriver:
    """Hardened Docker driver per docs/15 §4 and ADR-0006.

    Workspace is streamed in as a tar over stdin into a tmpfs (`/work`), so
    there are no host mounts and no Docker socket inside. `/out` is a tmpfs
    whose files the entrypoint emits on stdout. `target-only` creates a per-run
    `--internal` network containing only the target and the check runner, and
    only after the scope decision is re-validated.

    STATUS: argument construction and reaping are unit-tested with a fake
    command runner. The `none` network path runs in real containers in the CI
    docker-sandbox job (tests/test_docker_sandbox_live.py). The `target-only`
    path and the check harness are not yet executed in Docker (INFRA-005).
    """

    name = "docker"
    isolation_level = "docker-hardened"

    def __init__(
        self,
        *,
        image: str | None = None,
        target_image: str | None = None,
        runner: CommandRunner | None = None,
        docker_bin: str = "docker",
    ) -> None:
        self.image = image or os.environ.get("SANDBOX_IMAGE", "")
        self.target_image = target_image or os.environ.get("SANDBOX_TARGET_IMAGE", self.image)
        if "@sha256:" not in self.image and os.environ.get("SANDBOX_ALLOW_UNPINNED_IMAGE") != "1":
            raise PlatformError(ErrorCode.SANDBOX_START_FAILED, "SANDBOX_IMAGE must be pinned by digest")
        self.runner = runner or _default_runner
        self.docker = docker_bin

    def hardening_args(self, spec: SandboxSpec, run_id: str) -> list[str]:
        lim = spec.limits
        args = [
            "--user",
            "65534:65534",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--tmpfs",
            "/work:rw,nosuid,size=512m,uid=65534",
            "--tmpfs",
            "/out:rw,noexec,nosuid,size=64m,uid=65534",
            "--cpus",
            str(lim.cpus),
            "--memory",
            f"{lim.memory_mb}m",
            "--memory-swap",
            f"{lim.memory_mb}m",
            "--pids-limit",
            str(lim.pids),
            "--label",
            f"{LABEL_ROOT}=1",
            "--label",
            f"{LABEL_ROOT}.run_id={run_id}",
            "--label",
            f"{LABEL_ROOT}.created={int(time.time())}",
            "--label",
            f"{LABEL_ROOT}.timeout={int(lim.timeout_s)}",
        ]
        for k, v in sorted(spec.labels.items()):
            args += ["--label", f"{LABEL_ROOT}.{k}={v}"]
        return args

    def build_run_argv(self, spec: SandboxSpec, run_id: str, network_name: str | None) -> list[str]:
        net = "none" if spec.network == "none" else network_name
        if net is None:
            raise PlatformError(ErrorCode.SCOPE_DENIED, "no authorised network")
        env = [
            "-e",
            "SANDBOX_OUT=/out",
            "-e",
            f"SANDBOX_NETWORK={'none' if spec.network == 'none' else 'target-only'}",
            "-e",
            "SANDBOX_EMIT_OUT=1",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
        ]
        if spec.network == "target-only":
            env += ["-e", f"SANDBOX_TARGET_URL=http://tgt-{run_id}:8000"]
        script = 'tar -x -C /work -f - && cd /work && exec python -I -B .sandbox/entry.py "$@"'
        return [
            self.docker,
            "run",
            "--rm",
            "-i",
            "--name",
            f"sbx-{run_id}",
            "--network",
            net,
            *self.hardening_args(spec, run_id),
            *env,
            "--workdir",
            "/work",
            "--entrypoint",
            "sh",
            self.image,
            "-c",
            script,
            "entry",
            spec.mode,
            *spec.args,
        ]

    def run(self, spec: SandboxSpec) -> SandboxResult:
        validate_spec(spec)
        run_id = new_id("sbx").lower().replace("_", "-")
        started = datetime.now(UTC)
        network_name: str | None = None
        root = Path(tempfile.mkdtemp(prefix=f"{run_id}-"))
        try:
            ws = _stage_workspace(spec, root)
            tar_bytes = subprocess.run(
                ["tar", "-c", "-C", str(ws), "."], capture_output=True, check=True
            ).stdout
            if spec.network == "target-only":
                network_name = f"net-{run_id}"
                self._ok(
                    self.runner(
                        [
                            self.docker,
                            "network",
                            "create",
                            "--internal",
                            "--label",
                            f"{LABEL_ROOT}=1",
                            "--label",
                            f"{LABEL_ROOT}.run_id={run_id}",
                            network_name,
                        ],
                        None,
                        30,
                    )
                )
                self._ok(
                    self.runner(
                        [
                            self.docker,
                            "run",
                            "-d",
                            "--name",
                            f"tgt-{run_id}",
                            "--network",
                            network_name,
                            *self.hardening_args(spec, run_id),
                            self.target_image,
                        ],
                        None,
                        60,
                    )
                )
            t0 = time.monotonic()
            try:
                cp = self.runner(
                    self.build_run_argv(spec, run_id, network_name), tar_bytes, spec.limits.timeout_s
                )
                timed_out = False
            except subprocess.TimeoutExpired:
                self.runner([self.docker, "rm", "-f", f"sbx-{run_id}"], None, 30)
                cp = subprocess.CompletedProcess([], -1, b"", b"timeout")
                timed_out = True
            stdout = cp.stdout.decode("utf-8", "replace")
            out_files: dict[str, bytes] = {}
            marker = "\n@@SANDBOX_OUT@@"
            if marker in stdout:
                stdout, payload = stdout.rsplit(marker, 1)
                try:
                    out_files = {k: base64.b64decode(v) for k, v in json.loads(payload).items()}
                except (ValueError, json.JSONDecodeError):
                    out_files = {}
            return SandboxResult(
                run_id=run_id,
                driver=self.name,
                isolation_level=self.isolation_level,
                profile=spec.profile.value,
                network=spec.network,
                exit_code=None if timed_out else cp.returncode,
                stdout=_cap(stdout),
                stderr=_cap(cp.stderr.decode("utf-8", "replace")),
                out_files=out_files,
                duration_s=time.monotonic() - t0,
                timed_out=timed_out,
                started_at=started,
                labels=dict(spec.labels),
            )
        finally:
            if network_name:
                self.runner([self.docker, "rm", "-f", f"tgt-{run_id}"], None, 30)
                self.runner([self.docker, "network", "rm", network_name], None, 30)
            shutil.rmtree(root, ignore_errors=True)

    def reap(self, now: float | None = None) -> list[str]:
        """Remove sandbox containers older than 2x their timeout. Returns removed names."""
        now = now or time.time()
        cp = self.runner(
            [
                self.docker,
                "ps",
                "-a",
                "--filter",
                f"label={LABEL_ROOT}=1",
                "--format",
                '{{.Names}}\t{{.Label "'
                + LABEL_ROOT
                + '.created"}}\t{{.Label "'
                + LABEL_ROOT
                + '.timeout"}}',
            ],
            None,
            30,
        )
        removed: list[str] = []
        for line in cp.stdout.decode().splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            name, created, timeout = parts
            try:
                age = now - float(created)
                limit = 2 * float(timeout)
            except ValueError:
                continue
            if age > limit:
                self.runner([self.docker, "rm", "-f", name], None, 30)
                removed.append(name)
        return removed

    @staticmethod
    def _ok(cp: subprocess.CompletedProcess[bytes]) -> None:
        if cp.returncode != 0:
            raise PlatformError(ErrorCode.SANDBOX_START_FAILED, cp.stderr.decode("utf-8", "replace")[:300])
