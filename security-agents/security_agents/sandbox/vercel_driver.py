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
import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from ..contracts import ErrorCode, PlatformError, new_id
from . import node
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
BASE_SNAPSHOT_TTL = 7 * 24 * 3600  # rebuilt on first use after expiry
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

# node_http targets (ADR-0023). Node is the official tarball pinned by sha256; the platform
# packages come from security-agents/sandbox/node's lockfile; firebase-tools itself checks
# the emulator JAR it fetches. None of it is derived from the repository under test.
NODE_VERSION = "v22.23.4"
NODE_SHA256 = {
    "x86_64": "1805bcd35e6815559bd2eb97db438d3fdb0eb3a5e6a977b7c1badca76337e9ce",
    "aarch64": "6287aa46b6c375d816e63ae66d024fbbfd70404825aabdfdf898a970871d2f4b",
}
NODE_DOMAINS = ("nodejs.org", "registry.npmjs.org", "storage.googleapis.com")
NPM_DOMAINS = ("registry.npmjs.org",)
JRE_APT = ("openjdk-21-jre-headless", "xz-utils", "curl", "ca-certificates")
ARI_NODE = "/opt/ari-node"
ARI_DEPS = "/opt/ari-deps"
EMULATORS_PATH = f"{ARI_NODE}/emulators"
NODE_PORTS = {"auth": 9099, "firestore": 8080, "ws": 9150, "hub": 4400, "logging": 4500, "app": 8000}
NODE_LOG = "/tmp/node_stack.log"
NODE_OUT = "/tmp/node_stack.out"
NODE_INSTALL = (
    'set -e; arch=$(uname -m); case "$arch" in x86_64) a=x64;; aarch64) a=arm64;; *) exit 3;; esac; '
    "f=node-$1-linux-$a.tar.xz; cd /tmp && curl -fsSLO https://nodejs.org/dist/$1/$f && "
    'echo "$( [ $arch = x86_64 ] && echo $2 || echo $3 )  $f" | sha256sum -c - && '
    "mkdir -p /opt/node && tar -xJf $f -C /opt/node --strip-components=1 && "
    "ln -sf /opt/node/bin/node /opt/node/bin/npm /opt/node/bin/npx /usr/local/bin/"
)


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
        has_lock = spec.node_stack is not None and (spec.workspace / "package-lock.json").is_file()
        if has_lock and (problems := node.lockfile_problems(spec.workspace)):
            raise PlatformError(ErrorCode.SANDBOX_POLICY_VIOLATION, "; ".join(problems))
        root = Path(tempfile.mkdtemp(prefix=f"{run_id}-"))
        box: VercelBox | None = None
        target_log = ""
        t0 = time.monotonic()
        try:
            ws = _stage_workspace(spec, root)
            if spec.node_stack is not None:
                config = {
                    **spec.node_stack,
                    "node_dir": ARI_NODE,
                    "ports": NODE_PORTS,
                    "emulators_path": EMULATORS_PATH,
                }
                (ws / ".sandbox" / "node_stack.json").write_text(json.dumps(config), encoding="utf-8")
                (ws / ".sandbox" / "node_stack.mjs").write_bytes(node.LAUNCHER.read_bytes())
            ws_tar = _tar(ws)
            box = self._factory(spec, run_id, needs_target)
            box.put_archive(ws_tar, WORKDIR)

            env = {
                "SANDBOX_OUT": "/tmp/out",
                "SANDBOX_NETWORK": "none" if spec.network == "none" else "target-only",
                "SANDBOX_EMIT_OUT": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
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
            if spec.node_stack is not None:
                env.update(_start_node_stack(box, spec, has_lock))

            exit_code, stdout, stderr, timed_out = box.run(
                ["python", "-I", "-B", ".sandbox/entry.py", spec.mode, *spec.args],
                cwd=WORKDIR,
                env=env,
                timeout=spec.limits.timeout_s,
            )
            if needs_target:
                target_log = _cap(box.logs())
            if spec.node_stack is not None:
                target_log = _cap(box.run(["cat", NODE_LOG], cwd=WORKDIR, env={}, timeout=10)[1])
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


def _start_node_stack(box: VercelBox, spec: SandboxSpec, has_lock: bool) -> dict[str, str]:
    """Start the launcher in the run box and wait for it; returns the entry's extra env."""
    assert spec.node_stack is not None
    if has_lock:
        box.run(["ln", "-s", f"{ARI_DEPS}/node_modules", "node_modules"], cwd=WORKDIR, env={}, timeout=10)
    box.start(
        ["sh", "-c", f"exec node .sandbox/node_stack.mjs .sandbox/node_stack.json >{NODE_OUT} 2>{NODE_LOG}"],
        cwd=WORKDIR,
        env={"NODE_ENV": "production"},
    )
    for _ in range(240):  # emulators take ~10-30 s to boot
        code, _out, _err, _timed = box.run(
            ["grep", "-q", node.READY, NODE_OUT], cwd=WORKDIR, env={}, timeout=5
        )
        if code == 0:
            break
        time.sleep(0.5)
    else:
        log = box.run(["tail", "-c", "800", NODE_LOG], cwd=WORKDIR, env={}, timeout=5)[1]
        raise PlatformError(ErrorCode.SANDBOX_START_FAILED, "node target did not start: " + log)
    emulators = spec.node_stack.get("emulators") or []
    env = {"ARI_NODE_DIR": ARI_NODE}
    if "firestore" in emulators:  # type: ignore[operator]
        env["FIRESTORE_EMULATOR_HOST"] = f"127.0.0.1:{NODE_PORTS['firestore']}"
    if "auth" in emulators:  # type: ignore[operator]
        env["FIREBASE_AUTH_EMULATOR_HOST"] = f"127.0.0.1:{NODE_PORTS['auth']}"
    if spec.node_stack.get("serve"):
        env["SANDBOX_TARGET_URL"] = f"http://127.0.0.1:{NODE_PORTS['app']}"
    return env


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


def _req_name(req: str) -> str:
    """Distribution name of a pip requirement, normalized like pip itself."""
    name = re.split(r"[<>=!~;\[\s]", req, maxsplit=1)[0]
    return name.strip().lower().replace("_", "-")


# The sandbox entry's test-tamper audit hooks into pytest/pluggy internals; a customer
# recipe must never choose those versions, or it could weaken Verify's own checks.
PROTECTED_RUNNER_DISTRIBUTIONS = frozenset({"pytest", "pluggy"})


def _merged_pip(runner: tuple[str, ...], extra: Iterable[str]) -> list[str]:
    """Runner wheels plus the recipe's packages, one requirement per distribution.

    When the recipe pins an application distribution the runner also pins (fastapi,
    pydantic, ...), the recipe's pin wins: pip cannot satisfy two pins of one name in a
    single install, and the recipe states the versions the target's code actually needs.
    Pins of the audit toolchain (PROTECTED_RUNNER_DISTRIBUTIONS) are dropped instead.
    """
    kept = [r for r in extra if _req_name(r) not in PROTECTED_RUNNER_DISTRIBUTIONS]
    overridden = {_req_name(r) for r in kept}
    return [r for r in runner if _req_name(r) not in overridden] + kept


def _platform_node_lock() -> str:
    return hashlib.sha256((node.NODE_DIR / "package-lock.json").read_bytes()).hexdigest()


def _base_key(spec: SandboxSpec) -> str:
    material = json.dumps([RUNNER_WHEELS, sorted(spec.pip), sorted(spec.apt), APT_HTTPS])
    if getattr(spec, "node_stack", None) is not None:
        material += json.dumps([NODE_VERSION, NODE_SHA256, JRE_APT, _platform_node_lock()])
    return hashlib.sha256(material.encode()).hexdigest()[:24]


def _base_index() -> Path:
    root = Path(os.environ.get("SECURITY_WORKDIR") or tempfile.gettempdir())
    root.mkdir(parents=True, exist_ok=True)
    return root / "sandbox-bases.json"


_SWEPT_AT = 0.0


def _sweep_stale() -> None:  # pragma: no cover - live
    """Best effort, at most every 10 minutes per process: destroy run sandboxes a killed
    worker left behind (stopped, or older than any run may last). Orphan snapshots of
    those sandboxes go with them: named boxes snapshot on stop, and leaked snapshots
    exhaust the account's snapshot storage (HTTP 402). Snapshots the run box did not
    create — including the shared base — are never "orphans" of it, so they survive."""
    global _SWEPT_AT
    if time.time() - _SWEPT_AT < 600:
        return
    _SWEPT_AT = time.time()
    from vercel.sandbox import sync as vsandbox

    with _suppress():
        cutoff_ms = (time.time() - 3 * 3600) * 1000
        for sb in vsandbox.query_sandboxes():
            name = sb.name or ""
            stale = (
                str(getattr(sb.status, "value", sb.status)) == "stopped" or (sb.created_at or 0) < cutoff_ms
            )
            if name.startswith("ari-sbx-") and stale:
                with _suppress():
                    vsandbox.get_sandbox(name=name).destroy(delete_orphan_snapshots=True)


def _base_snapshot(spec: SandboxSpec, *, rebuild: bool = False) -> str:  # pragma: no cover - live
    """Snapshot id of a sandbox with this spec's packages installed, built once per package
    set and shared by every worker in the container (file lock)."""
    import fcntl

    _sweep_stale()
    key, index = _base_key(spec), _base_index()
    with open(index.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        known = json.loads(index.read_text()) if index.is_file() else {}
        if key in known and not rebuild:
            return str(known[key])
        known[key] = _build_base(spec, key)
        index.write_text(json.dumps(known))
        return str(known[key])


def _build_base(spec: SandboxSpec, key: str) -> str:  # pragma: no cover - live
    """Install packages in a throwaway builder with egress limited to PyPI (and the HTTPS
    Ubuntu mirrors when apt is needed; nodejs.org, the npm registry and the emulator host
    for node targets), snapshot it, destroy the builder. No repository code is ever in it."""
    from vercel.sandbox import NetworkPolicy
    from vercel.sandbox import sync as vsandbox

    wants_node = getattr(spec, "node_stack", None) is not None
    apt = (*spec.apt, *(JRE_APT if wants_node else ()))
    domains = PYPI_DOMAINS + (UBUNTU_DOMAINS if apt else ()) + (NODE_DOMAINS if wants_node else ())
    box = vsandbox.create_sandbox(
        name=f"ari-base-{key}-{int(time.time())}",
        execution_time_limit=1500 if wants_node else 900,
        network_policy=NetworkPolicy.custom(dict.fromkeys(domains, ())),
        persistent=False,
        destroy=False,
    )
    try:
        if apt:
            env = {"DEBIAN_FRONTEND": "noninteractive"}
            # The egress allowlist passes TLS only: use the HTTPS Ubuntu mirrors and drop
            # third-party lists (e.g. cli.github.com) that are not allowed.
            box.run_process("sh", ["-c", APT_HTTPS], sudo=True, check=True, capture_output=True)
            box.run_process("apt-get", ["update", "-qq"], sudo=True, env=env, check=True, capture_output=True)
            box.run_process(
                "apt-get",
                ["install", "-y", "-qq", "--no-install-recommends", *apt],
                sudo=True,
                env=env,
                check=True,
                capture_output=True,
            )
        box.run_process(
            "python",
            [
                "-m",
                "pip",
                "install",
                "-q",
                "--root-user-action=ignore",
                "--only-binary=:all:",
                *_merged_pip(RUNNER_WHEELS, spec.pip),
            ],
            sudo=True,  # system site-packages: the entry runs `python -I`, which skips user site
            check=True,
            capture_output=True,
        )
        if wants_node:
            box.run_process(
                "sh",
                ["-c", NODE_INSTALL, "sh", NODE_VERSION, NODE_SHA256["x86_64"], NODE_SHA256["aarch64"]],
                sudo=True,
                check=True,
                capture_output=True,
            )
            box.run_process(
                "sh", ["-c", f"mkdir -p {ARI_NODE} && chmod 777 {ARI_NODE}"], sudo=True, check=True
            )
            for name in ("package.json", "package-lock.json"):
                box.fs.write_bytes(f"{ARI_NODE}/{name}", (node.NODE_DIR / name).read_bytes())
            box.run_process(
                "npm",
                ["ci", "--ignore-scripts", "--no-audit", "--no-fund"],
                cwd=ARI_NODE,
                check=True,
                capture_output=True,
            )
            box.run_process(
                "node",
                [f"{ARI_NODE}/node_modules/firebase-tools/lib/bin/firebase.js", "setup:emulators:firestore"],
                cwd=ARI_NODE,
                env={"FIREBASE_EMULATORS_PATH": EMULATORS_PATH, "FIREBASE_CLI_DISABLE_UPDATE_CHECK": "true"},
                check=True,
                capture_output=True,
            )
        return str(box.snapshot(expiration=BASE_SNAPSHOT_TTL).id)
    finally:
        with _suppress():
            box.stop()
        with _suppress():
            box.destroy(delete_orphan_snapshots=False)


def _deps_snapshot(
    spec: SandboxSpec, base_id: str, *, rebuild: bool = False
) -> str:  # pragma: no cover - live
    """Snapshot of the base plus the target's node_modules, one per lockfile. The builder
    receives only package.json and package-lock.json and installs with --ignore-scripts,
    egress limited to the npm registry: no repository code runs while egress is open."""
    import fcntl

    from vercel.sandbox import NetworkPolicy, SnapshotSource
    from vercel.sandbox import sync as vsandbox

    key, index = f"deps-{base_id}-{node.lock_key(spec.workspace)}", _base_index()
    with open(index.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        known = json.loads(index.read_text()) if index.is_file() else {}
        if key in known and not rebuild:
            return str(known[key])
        box = vsandbox.create_sandbox(
            name=f"ari-deps-{node.lock_key(spec.workspace)}-{int(time.time())}",
            source=SnapshotSource(snapshot_id=base_id),
            execution_time_limit=900,
            network_policy=NetworkPolicy.custom(dict.fromkeys(NPM_DOMAINS, ())),
            persistent=False,
            destroy=False,
        )
        try:
            box.run_process(
                "sh", ["-c", f"mkdir -p {ARI_DEPS} && chmod 777 {ARI_DEPS}"], sudo=True, check=True
            )
            for name in ("package.json", "package-lock.json"):
                box.fs.write_bytes(f"{ARI_DEPS}/{name}", (spec.workspace / name).read_bytes())
            box.run_process(
                "npm",
                ["ci", "--ignore-scripts", "--no-audit", "--no-fund", f"--registry={node.REGISTRY}"],
                cwd=ARI_DEPS,
                check=True,
                capture_output=True,
            )
            known[key] = str(box.snapshot(expiration=BASE_SNAPSHOT_TTL).id)
        finally:
            with _suppress():
                box.stop()
            with _suppress():
                box.destroy(delete_orphan_snapshots=False)
        index.write_text(json.dumps(known))
        return str(known[key])


def _run_snapshot(spec: SandboxSpec, *, rebuild: bool = False) -> str:  # pragma: no cover - live
    base = _base_snapshot(spec, rebuild=rebuild)
    if getattr(spec, "node_stack", None) is not None and (spec.workspace / "package-lock.json").is_file():
        return _deps_snapshot(spec, base, rebuild=rebuild)
    return base


class _VercelSdkBox:  # pragma: no cover - requires live Vercel credentials
    """Real Vercel Sandbox, created with deny-all egress. Destroyed by `stop()`.

    Named sandboxes snapshot on stop; without destroy those snapshots leak and exhaust
    the account's snapshot storage (HTTP 402), so `stop()` destroys them too."""

    def __init__(self, spec: SandboxSpec, run_id: str) -> None:
        from vercel.sandbox import NetworkPolicy, SnapshotSource
        from vercel.sandbox import sync as vsandbox

        common = {
            "name": f"ari-{run_id}",
            "execution_time_limit": int(spec.limits.timeout_s) + 240,
            "tags": {k[:63]: v[:200] for k, v in spec.labels.items()},
            "persistent": False,
            "destroy": False,
        }
        # Boot from a snapshot that already holds the runner wheels and the recipe's
        # packages: no install window, and deny-all egress from the first instant.
        try:
            self._box = vsandbox.create_sandbox(
                source=SnapshotSource(snapshot_id=_run_snapshot(spec)),
                network_policy=NetworkPolicy.deny_all(),
                **common,
            )
        except Exception:  # the base expired or was removed: build a new one, once
            self._box = vsandbox.create_sandbox(
                source=SnapshotSource(snapshot_id=_run_snapshot(spec, rebuild=True)),
                network_policy=NetworkPolicy.deny_all(),
                **common,
            )
        self._teardown: threading.Thread | None = None

    def put_archive(self, tar_bytes: bytes, dest: str) -> None:
        self._box.fs.write_bytes("/tmp/stage.tar", tar_bytes)
        # Directories are made in the same process as the unpack: one round trip, not four.
        self._box.run_process(
            "sh",
            ["-c", 'mkdir -p "$1" /tmp/out && tar -xf /tmp/stage.tar -C "$1"', "sh", dest],
            check=True,
        )

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
        # Teardown is off the critical path; a box this process does not finish is swept later.
        self._teardown = threading.Thread(target=self._destroy, daemon=True)
        self._teardown.start()

    def _destroy(self) -> None:
        try:
            with _suppress():
                self._box.stop()
        finally:
            # The shared base snapshot must survive; non-persistent boxes make none of their own.
            with _suppress():
                self._box.destroy(delete_orphan_snapshots=False)
