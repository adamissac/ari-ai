"""VercelSandboxDriver: a fake microVM verifies staging, the entry command, the deny-all
boundary, out-file collection and that the sandbox is always destroyed. No live Vercel."""

from __future__ import annotations

import base64
import io
import json
import tarfile
from pathlib import Path
from typing import ClassVar

import pytest

from security_agents.contracts import ErrorCode, PlatformError
from security_agents.sandbox.driver import SandboxProfile, SandboxSpec
from security_agents.sandbox.vercel_driver import WORKDIR, VercelSandboxDriver


class FakeBox:
    """Records what the driver stages and runs; emits the entry OUT marker."""

    from typing import ClassVar

    instances: ClassVar[list[FakeBox]] = []

    def __init__(self, spec: SandboxSpec, run_id: str, needs_target: bool) -> None:
        self.spec = spec
        self.archives: dict[str, bytes] = {}
        self.ran: list[tuple[list[str], str, dict[str, str]]] = []
        self.started: list[list[str]] = []
        self.stopped = False
        FakeBox.instances.append(self)

    # VercelBox protocol
    def put_archive(self, tar_bytes: bytes, dest: str) -> None:
        self.archives[dest] = tar_bytes

    def run(self, argv, *, cwd, env, timeout):
        self.ran.append((argv, cwd, env))
        if argv[:1] == ["python"] and "socket.create_connection" in " ".join(argv):
            return 0, "", "", False  # readiness probe
        out = base64.b64encode(b'{"passed": 1}').decode()
        payload = json.dumps({"result.json": out})
        return 0, f"collected 1 item\n@@SANDBOX_OUT@@{payload}\n", "", False

    def start(self, argv, *, cwd, env):
        self.started.append(argv)

    def logs(self) -> str:
        return "target up"

    def stop(self) -> None:
        self.stopped = True


@pytest.fixture(autouse=True)
def _reset():
    FakeBox.instances.clear()
    yield


def _driver() -> VercelSandboxDriver:
    return VercelSandboxDriver(factory=FakeBox)


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "snapshot"
    (ws / "tests").mkdir(parents=True)
    (ws / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")
    return ws


def _names(tar_bytes: bytes) -> set[str]:
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as t:
        return {m.name for m in t.getmembers()}


def test_runs_entry_in_the_microvm_and_collects_out_files(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    spec = SandboxSpec(
        profile=SandboxProfile.TEST_RUNNER,
        network="none",
        workspace=ws,
        mode="pytest",
        args=["-q", "tests"],
        labels={"assessment_id": "asm", "step_key": "s"},
    )
    result = _driver().run(spec)

    assert result.driver == "vercel-sandbox"
    assert result.isolation_level == "microvm"
    assert result.exit_code == 0
    assert result.out_files == {"result.json": b'{"passed": 1}'}
    assert "@@SANDBOX_OUT@@" not in result.stdout  # marker stripped from the visible output

    box = FakeBox.instances[0]
    assert box.stopped is True  # always destroyed
    # The staged workspace carries the entry bootstrap and the target's own tests.
    names = _names(box.archives[WORKDIR])
    assert "./.sandbox/entry.py" in names
    assert "./tests/test_x.py" in names
    # The one command is the fixed entry dispatch, never model-authored.
    entry = next(r for r in box.ran if ".sandbox/entry.py" in r[0])
    assert entry[0] == ["python", "-I", "-B", ".sandbox/entry.py", "pytest", "-q", "tests"]
    assert entry[2]["SANDBOX_NETWORK"] == "none"
    assert "SANDBOX_TARGET_URL" not in entry[2]


def test_destroys_the_sandbox_even_when_the_run_raises(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)

    class Boom(FakeBox):
        def run(self, argv, *, cwd, env, timeout):
            raise RuntimeError("kaboom")

    spec = SandboxSpec(
        profile=SandboxProfile.TEST_RUNNER,
        network="none",
        workspace=ws,
        mode="pytest",
        args=["-q"],
        labels={"assessment_id": "asm", "step_key": "s"},
    )
    with pytest.raises(RuntimeError):
        VercelSandboxDriver(factory=Boom).run(spec)
    assert FakeBox.instances[0].stopped is True


def test_rejects_a_workspace_at_a_forbidden_root() -> None:
    spec = SandboxSpec(
        profile=SandboxProfile.TEST_RUNNER,
        network="none",
        workspace=Path("/etc"),
        mode="pytest",
        args=[],
        labels={},
    )
    with pytest.raises(PlatformError) as exc:
        _driver().run(spec)
    assert exc.value.code == ErrorCode.SANDBOX_POLICY_VIOLATION
    assert FakeBox.instances == []  # never created a sandbox


def test_sdk_box_locks_egress_before_staging_and_destroys_snapshots(monkeypatch) -> None:
    """Runner wheels install with PyPI-only egress; deny-all lands before any repo code."""
    from types import SimpleNamespace

    from vercel.sandbox import NetworkPolicy
    from vercel.sandbox import sync as vsandbox

    from security_agents.sandbox import vercel_driver

    calls: list[tuple] = []

    class Box:
        fs = SimpleNamespace(mkdir=lambda d, **kw: calls.append(("mkdir", d)))

        def run_process(self, cmd, args, **kw):
            calls.append(("run", cmd, tuple(args), kw.get("sudo")))

        def update_network_policy(self, policy):
            calls.append(("policy", policy.mode))

        def stop(self):
            calls.append(("stop",))

        def destroy(self, *, delete_orphan_snapshots=False):
            calls.append(("destroy", delete_orphan_snapshots))

    def create(**kw):
        calls.append(("create", kw["network_policy"].mode, kw["persistent"]))
        assert set(kw["network_policy"].allow) == set(vercel_driver.PYPI_DOMAINS)
        return Box()

    monkeypatch.setattr(vsandbox, "create_sandbox", create)
    spec = SimpleNamespace(limits=SimpleNamespace(timeout_s=60), labels={})
    box = vercel_driver._VercelSdkBox(spec, "r1")
    box.stop()

    assert calls[0] == ("create", "custom", False)
    assert calls[1][:2] == ("run", "python") and calls[1][3] is True
    assert calls[2] == ("policy", NetworkPolicy.deny_all().mode)
    assert all(c[0] == "mkdir" for c in calls[3:6])
    assert calls[-2:] == [("stop",), ("destroy", True)]
