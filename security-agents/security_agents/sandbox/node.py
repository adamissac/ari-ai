"""Node target support shared by the drivers (ADR-0023).

The launcher (`node_stack.mjs`) and the platform packages (`security-agents/sandbox/node/`)
are platform-owned. The target's own dependencies are installed from its lockfile only,
with `--ignore-scripts`, so no repository code runs while the registry is reachable.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import IO, Any

from ..contracts import ErrorCode, PlatformError

LAUNCHER = Path(__file__).with_name("node_stack.mjs")
NODE_DIR = Path(os.environ.get("ARI_NODE_DIR") or Path(__file__).resolve().parents[2] / "sandbox" / "node")
REGISTRY = "https://registry.npmjs.org/"
READY = "@@ARI_READY@@"


def lockfile_problems(workspace: Path) -> list[str]:
    """Refuse anything `npm ci --ignore-scripts` could fetch from outside the npm registry."""
    lock = workspace / "package-lock.json"
    if not lock.is_file():
        return ["package-lock.json is required (npm ci installs exactly the lockfile)"]
    try:
        data = json.loads(lock.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return ["package-lock.json is not valid JSON"]
    bad = [
        name
        for name, pkg in (data.get("packages") or {}).items()
        if name
        and isinstance(pkg, dict)
        and pkg.get("resolved")
        and not str(pkg["resolved"]).startswith(REGISTRY)
        and not pkg.get("link")
    ]
    return [f"dependencies resolved outside {REGISTRY}: {bad[:5]}"] if bad else []


def lock_key(workspace: Path) -> str:
    return hashlib.sha256((workspace / "package-lock.json").read_bytes()).hexdigest()[:24]


def ensure_node_modules(workspace: Path, cache_root: Path | None = None) -> Path:
    """DEV path (local driver): the target's node_modules, installed once per lockfile in a
    builder directory holding only package.json and package-lock.json."""
    problems = lockfile_problems(workspace)
    if problems:
        raise PlatformError(ErrorCode.SANDBOX_POLICY_VIOLATION, "; ".join(problems))
    root = cache_root or Path(os.environ.get("SECURITY_WORKDIR") or tempfile.gettempdir()) / "node-deps"
    target = root / lock_key(workspace)
    if (target / "node_modules").is_dir():
        return target / "node_modules"
    build = Path(tempfile.mkdtemp(prefix="ari-npm-", dir=root.parent if root.parent.is_dir() else None))
    for name in ("package.json", "package-lock.json"):
        shutil.copy2(workspace / name, build / name)
    cp = subprocess.run(
        ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund", f"--registry={REGISTRY}"],
        cwd=build,
        capture_output=True,
        text=True,
        timeout=600,
        env={"PATH": _path(), "HOME": str(build), "npm_config_cache": str(build / ".npm")},
    )
    if cp.returncode != 0:
        shutil.rmtree(build, ignore_errors=True)
        raise PlatformError(ErrorCode.SANDBOX_START_FAILED, f"npm ci failed: {cp.stderr[-500:]}")
    target.mkdir(parents=True, exist_ok=True)
    shutil.move(str(build / "node_modules"), target / "node_modules")
    shutil.rmtree(build, ignore_errors=True)
    return target / "node_modules"


def _path() -> str:
    node = shutil.which("node")
    if node is None:
        raise PlatformError(ErrorCode.SANDBOX_START_FAILED, "node is not installed")
    return f"{os.path.dirname(node)}:/usr/bin:/bin"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def ports() -> dict[str, int]:
    return {name: _free_port() for name in ("auth", "firestore", "ws", "hub", "logging", "app")}


class LocalStack:
    """The launcher as a host subprocess (local driver only; not a security boundary)."""

    def __init__(
        self, workspace: Path, config: dict[str, Any], scratch: Path, timeout_s: float = 120
    ) -> None:
        self.config = {**config, "node_dir": str(NODE_DIR), "ports": ports()}
        cfg = scratch / "node_stack.json"
        cfg.write_text(json.dumps(self.config), encoding="utf-8")
        self.log_path = scratch / "node_stack.log"
        self._log: IO[str] = self.log_path.open("w")
        self.proc = subprocess.Popen(
            ["node", str(LAUNCHER), str(cfg)],
            cwd=workspace,
            env={"PATH": _path(), "HOME": str(scratch), "TMPDIR": str(scratch), "LANG": "C.UTF-8"},
            stdout=subprocess.PIPE,
            stderr=self._log,
            text=True,
            start_new_session=True,
        )
        deadline = time.monotonic() + timeout_s
        assert self.proc.stdout is not None
        while True:
            line = self.proc.stdout.readline()
            if READY in line:
                break
            if (not line and self.proc.poll() is not None) or time.monotonic() > deadline:
                self.stop()
                raise PlatformError(
                    ErrorCode.SANDBOX_START_FAILED, "node target did not start: " + self.log()[-800:]
                )

    def env(self) -> dict[str, str]:
        p = self.config["ports"]
        out = {"ARI_NODE_DIR": str(NODE_DIR), "PATH": _path()}
        if "firestore" in self.config["emulators"]:
            out["FIRESTORE_EMULATOR_HOST"] = f"127.0.0.1:{p['firestore']}"
        if "auth" in self.config["emulators"]:
            out["FIREBASE_AUTH_EMULATOR_HOST"] = f"127.0.0.1:{p['auth']}"
        if self.config.get("serve"):
            out["SANDBOX_TARGET_URL"] = f"http://127.0.0.1:{p['app']}"
        return out

    def log(self) -> str:
        if not self._log.closed:
            self._log.flush()
        return self.log_path.read_text(encoding="utf-8", errors="replace")

    def stop(self) -> None:
        if self.proc.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.proc.pid, signal.SIGKILL)
        self.proc.wait(10)
        if self.proc.stdout is not None:
            self.proc.stdout.close()
        self._log.close()
