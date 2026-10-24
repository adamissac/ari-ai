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


def _fake_vercel(monkeypatch, tmp_path):
    """Record every SDK call the box and the base builder make."""
    from types import SimpleNamespace

    from vercel.sandbox import sync as vsandbox

    from security_agents.sandbox import vercel_driver

    calls: list[tuple] = []
    monkeypatch.setenv("SECURITY_WORKDIR", str(tmp_path))
    monkeypatch.setattr(vercel_driver, "_SWEPT_AT", 1e18)  # no sweeping in unit tests

    class Box:
        def __init__(self, kw):
            self.kw = kw
            self.fs = SimpleNamespace(write_bytes=lambda *a, **k: None)

        def run_process(self, cmd, args, **kw):
            calls.append(("run", cmd, tuple(args), kw.get("sudo")))

        def snapshot(self, expiration=None):
            calls.append(("snapshot", expiration))
            return SimpleNamespace(id="snap_base1")

        def stop(self):
            calls.append(("stop", self.kw["name"]))

        def destroy(self, *, delete_orphan_snapshots=False):
            calls.append(("destroy", self.kw["name"], delete_orphan_snapshots))

    def create(**kw):
        policy = kw["network_policy"]
        source = getattr(kw.get("source"), "snapshot_id", None)
        calls.append(("create", kw["name"], policy.mode, sorted(policy.allow), source, kw["persistent"]))
        return Box(kw)

    monkeypatch.setattr(vsandbox, "create_sandbox", create)
    spec = SimpleNamespace(
        limits=SimpleNamespace(timeout_s=60), labels={}, apt=("postgresql",), pip=("sqlalchemy==2.1.5",)
    )
    return calls, spec, vercel_driver


def test_base_is_built_once_with_package_egress_and_run_boxes_boot_deny_all(monkeypatch, tmp_path) -> None:
    calls, spec, vd = _fake_vercel(monkeypatch, tmp_path)
    for name in ("r1", "r2"):
        box = vd._VercelSdkBox(spec, name)
        box.stop()
        box._teardown.join(5)  # teardown runs off the critical path

    builds = [c for c in calls if c[0] == "create" and c[1].startswith("ari-base-")]
    runs = [c for c in calls if c[0] == "create" and not c[1].startswith("ari-base-")]
    assert len(builds) == 1  # the base is reused by the second box
    assert builds[0][2] == "custom" and set(builds[0][3]) == set(vd.PYPI_DOMAINS + vd.UBUNTU_DOMAINS)
    assert any(c[0] == "run" and c[1] == "python" and c[3] is True for c in calls)  # installs in the builder
    assert ("snapshot", vd.BASE_SNAPSHOT_TTL) in calls
    assert all(r[2] == "deny-all" and r[4] == "snap_base1" and r[5] is False for r in runs)
    # no repository code is ever in the builder; every sandbox is destroyed, the base kept
    assert all(c[2] is False for c in calls if c[0] == "destroy")
    assert {c[1] for c in calls if c[0] == "destroy"} == {builds[0][1], "ari-r1", "ari-r2"}


def test_sweep_destroys_stale_run_boxes_with_their_orphan_snapshots(monkeypatch) -> None:
    import time
    from types import SimpleNamespace

    from vercel.sandbox import sync as vsandbox

    from security_agents.sandbox import vercel_driver as vd

    now_ms = time.time() * 1000
    listed = [
        SimpleNamespace(name="ari-sbx-old", status="running", created_at=0),  # over the 3h cap
        SimpleNamespace(name="ari-sbx-done", status="stopped", created_at=now_ms),  # stopped
        SimpleNamespace(name="ari-sbx-live", status="running", created_at=now_ms),  # fresh: keep
        SimpleNamespace(name="ari-base-x", status="stopped", created_at=0),  # not a run box: keep
    ]
    destroyed: list[tuple[str, bool]] = []
    monkeypatch.setattr(vsandbox, "query_sandboxes", lambda: listed)
    monkeypatch.setattr(
        vsandbox,
        "get_sandbox",
        lambda *, name: SimpleNamespace(
            destroy=lambda *, delete_orphan_snapshots: destroyed.append((name, delete_orphan_snapshots))
        ),
    )
    monkeypatch.setattr(vd, "_SWEPT_AT", 0.0)
    vd._sweep_stale()
    assert destroyed == [("ari-sbx-old", True), ("ari-sbx-done", True)]
