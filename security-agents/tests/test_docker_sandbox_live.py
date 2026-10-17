from __future__ import annotations

import os
import shutil
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


def test_payments_lite_suite_runs_inside_the_hardened_container(tmp_path):
    source = Path(__file__).resolve().parents[2] / "examples" / "payments-lite" / "target"
    ws = tmp_path / "workspaces" / "payments_lite"
    shutil.copytree(source, ws, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    spec = SandboxSpec(
        profile=SandboxProfile.TEST_RUNNER,
        network="none",
        workspace=ws,
        mode="pytest",
        args=["-q", "tests"],
        labels={"purpose": "live_docker_check"},
        limits=SandboxLimits(timeout_s=180),
    )
    result = DockerSandboxDriver().run(spec)
    assert result.exit_code == 0, result.stdout[-2000:] + result.stderr[-2000:]
    assert " passed" in result.stdout and " failed" not in result.stdout


@pytest.fixture(scope="module")
def payments_intel(tmp_path_factory):
    from security_agents.contracts import new_id
    from security_agents.intel import LocalIntel
    from security_agents.sandbox.workspace import SnapshotHandle, copy_tree

    fixture = Path(__file__).resolve().parents[2] / "examples" / "payments-lite"
    root = tmp_path_factory.mktemp("docker_checks")
    staging = root / "staging"
    copy_tree(fixture / "target", staging)
    shutil.copy2(fixture / "build_recipe.json", staging / "build_recipe.json")
    snapshot = SnapshotHandle.from_directory(
        staging, root / "snapshot", snapshot_id=new_id("snp"), repo_id="rep_payments_lite"
    )
    return LocalIntel(snapshot)


def _docker_check(intel, template_ref: str, params: dict) -> dict:
    from datetime import UTC, datetime

    from security_agents.checks.library import default_library
    from security_agents.contracts import AgentName
    from security_agents.scope_guard import Decision
    from security_agents.tools import CheckRunner, ToolContext, recipe_from_snapshot

    runner = CheckRunner(
        driver=DockerSandboxDriver(),
        library=default_library(),
        workspace_provider=lambda _ctx: intel.snapshot.root,
        recipe_provider=recipe_from_snapshot(intel),
    )
    ctx = ToolContext(
        assessment_id="asm_docker",
        agent=AgentName.PROBE,
        run_id="run_docker",
        step_key="step",
        read_root=intel.snapshot.root,
    )
    ctx.artifacts["last_scope_decision"] = Decision(
        allowed=True, reason_code="OK", scope_id="scp_docker", evaluated_at=datetime.now(UTC)
    )
    return runner.run(ctx, template_ref, "tgt_payments_lite", params)


def test_ownership_check_in_docker_flags_the_planted_route(payments_intel):
    result = _docker_check(
        payments_intel,
        "access_control.ownership@1",
        {"route_id": "payment_detail", "owner_identity": "alice", "other_identity": "bob"},
    )
    assert result["matches_expectation"] is False, result
    assert result["network"] == "target-only"


def test_ownership_check_in_docker_clears_the_lookalike_route(payments_intel):
    result = _docker_check(
        payments_intel,
        "access_control.ownership@1",
        {"route_id": "customer_detail", "owner_identity": "alice", "other_identity": "bob"},
    )
    assert result["matches_expectation"] is True, result


def test_bounds_check_in_docker_flags_the_planted_defect(payments_intel):
    result = _docker_check(
        payments_intel,
        "input_validation.bounds@1",
        {
            "route_id": "create_refund",
            "read_route_id": "payment_detail",
            "owner_identity": "alice",
            "over_by": "1.00",
        },
    )
    assert result["matches_expectation"] is False, result
