from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from security_agents.sandbox.driver import (
    DockerSandboxDriver,
    SandboxLimits,
    SandboxProfile,
    SandboxSpec,
)

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("RUN_DOCKER_SANDBOX") != "1", reason="set RUN_DOCKER_SANDBOX=1 with a Docker engine"
    ),
]

PROBE = """
import os
from pathlib import Path

import pytest


def test_runs_as_nobody():
    assert os.getuid() == 65534 and os.getgid() == 65534


def test_root_filesystem_is_read_only():
    with pytest.raises(OSError):
        Path("/etc/sandbox-write-test").write_text("x")


def test_work_and_out_are_writable():
    Path("/work/ok.txt").write_text("x")
    Path("/out/ok.txt").write_text("x")


def test_kernel_network_is_isolated_without_the_python_guard():
    import _socket

    s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    s.settimeout(3)
    with pytest.raises(OSError):
        s.connect(("1.1.1.1", 53))


def test_host_environment_is_not_passed_in():
    assert "GITHUB_TOKEN" not in os.environ
    assert "SANDBOX_SECRET_CANARY" not in os.environ
    assert os.environ.get("SANDBOX_NETWORK") == "none"
"""

SLEEPER = """
import time


def test_sleeps_past_the_limit():
    time.sleep(60)
"""


def _workspace(tmp_path: Path, name: str, body: str) -> Path:
    ws = tmp_path / "workspaces" / name
    ws.mkdir(parents=True)
    (ws / f"test_{name}.py").write_text(body, encoding="utf-8")
    return ws


def _spec(ws: Path, name: str, limits: SandboxLimits) -> SandboxSpec:
    return SandboxSpec(
        profile=SandboxProfile.TEST_RUNNER,
        network="none",
        workspace=ws,
        mode="pytest",
        args=["-q", f"test_{name}.py"],
        labels={"purpose": "live_docker_check"},
        limits=limits,
    )


def test_real_container_enforces_user_filesystem_network_and_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_SECRET_CANARY", "must-not-leak")
    driver = DockerSandboxDriver()
    result = driver.run(_spec(_workspace(tmp_path, "probe", PROBE), "probe", SandboxLimits(timeout_s=120)))
    assert result.driver == "docker" and result.isolation_level == "docker-hardened"
    assert result.exit_code == 0, result.stdout[-2000:] + result.stderr[-2000:]
    assert "5 passed" in result.stdout
    assert "must-not-leak" not in result.stdout + result.stderr


def test_real_container_is_killed_and_removed_at_the_timeout(tmp_path):
    driver = DockerSandboxDriver()
    result = driver.run(
        _spec(_workspace(tmp_path, "sleeper", SLEEPER), "sleeper", SandboxLimits(timeout_s=8))
    )
    assert result.timed_out is True
    left = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name=sbx-{result.run_id}", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert left == ""
