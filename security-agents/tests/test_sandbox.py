"""Sandbox driver, workspace isolation and Docker argument policy (SEC-003, SB-03/04/05)."""

from __future__ import annotations

import os
import subprocess

import pytest

from security_agents.contracts import ErrorCode, PlatformError
from security_agents.sandbox.driver import (
    LABEL_ROOT,
    DockerSandboxDriver,
    LocalProcessDriver,
    SandboxLimits,
    SandboxProfile,
    SandboxSpec,
    validate_spec,
)
from security_agents.sandbox.workspace import (
    apply_diff,
    changed_paths,
    diff_paths,
    fresh_checkout,
    safe_rel_path,
    sha256_text,
    tree_digest,
    unified_diff,
)
from security_agents.scope_guard import Decision

from .conftest import NOW

ALLOWED = Decision(allowed=True, reason_code="OK", scope_id="scp_test", evaluated_at=NOW)
DENIED = Decision(allowed=False, reason_code="TARGET_NOT_IN_SCOPE", scope_id="scp_test", evaluated_at=NOW)


def spec_for(snapshot, **kw) -> SandboxSpec:
    base = dict(
        profile=SandboxProfile.TEST_RUNNER,
        network="none",
        workspace=snapshot.root,
        mode="pytest",
        args=["-q", "tests"],
        labels={"assessment_id": "asm", "step_key": "s"},
    )
    base.update(kw)
    return SandboxSpec(**base)


# --------------------------------------------------------------------------- paths


@pytest.mark.parametrize(
    "bad",
    ["/etc/passwd", "../x", "a/../../b", "", "x\x00y", "a\\b", ".git/config", "a/__pycache__/x"],
)
def test_safe_rel_path_rejects(bad):
    with pytest.raises(PlatformError) as exc:
        safe_rel_path(bad)
    assert exc.value.code is ErrorCode.SANDBOX_POLICY_VIOLATION


@pytest.mark.parametrize("good", ["a.py", "pkg/mod.py", "./pkg/mod.py", "tests/test_x.py"])
def test_safe_rel_path_normalises(good):
    assert safe_rel_path(good).startswith(("a.py", "pkg/", "tests/"))


def test_resolve_under_rejects_symlink_escape(tmp_path):
    from security_agents.sandbox.workspace import resolve_under

    root = tmp_path / "root"
    (root / "inside").mkdir(parents=True)
    secret = tmp_path / "outside.txt"
    secret.write_text("secret")
    (root / "link.txt").symlink_to(secret)
    with pytest.raises(PlatformError) as exc:
        resolve_under(root, "link.txt")
    assert exc.value.code is ErrorCode.SANDBOX_POLICY_VIOLATION


# --------------------------------------------------------------------------- snapshot


def test_snapshot_is_pinned_and_read_only(snapshot):
    digest_before = tree_digest(snapshot.root)
    target = snapshot.root / "payments_lite" / "app.py"
    with pytest.raises(PermissionError):
        target.write_text("tampered")
    assert tree_digest(snapshot.root) == digest_before
    # 40 hex chars so the value satisfies the canonical commit_sha contract,
    # with the real provenance recorded separately
    assert len(snapshot.commit_sha) == 40 and all(c in "0123456789abcdef" for c in snapshot.commit_sha)
    assert snapshot.pinned_by == "directory-digest"


def test_snapshot_from_git_pins_a_real_commit(tmp_path):
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "m.py").write_text("x = 1\n")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@e",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@e",
    }
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True, env=env)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True, env=env
    ).stdout.strip()
    from security_agents.sandbox.workspace import SnapshotHandle

    snap = SnapshotHandle.from_git(repo, sha, "pkg", tmp_path / "out", snapshot_id="snp", repo_id="rep")
    assert snap.commit_sha == sha and snap.pinned_by == "git"
    assert snap.files() == ["m.py"]


def test_fresh_checkout_is_writable_and_independent(snapshot, tmp_path):
    root = fresh_checkout(snapshot, tmp_path / "wt")
    (root / "payments_lite" / "app.py").write_text("changed\n")
    assert changed_paths(snapshot.root, root) == ["payments_lite/app.py"]
    assert (snapshot.root / "payments_lite" / "app.py").read_text() != "changed\n"


# --------------------------------------------------------------------------- diffs


def test_diff_round_trip_through_git_apply(snapshot, tmp_path):
    wt = fresh_checkout(snapshot, tmp_path / "wt")
    app = wt / "payments_lite" / "app.py"
    app.write_text(
        app.read_text().replace(
            "        return payment_out(store, p)",
            "        require_owner(p.customer_id, customer)\n        return payment_out(store, p)",
            1,
        )
    )
    (wt / "tests" / "test_authz.py").write_text("def test_x():\n    assert True\n")
    diff = unified_diff(snapshot.root, wt, changed_paths(snapshot.root, wt))
    assert set(diff_paths(diff)) == {"payments_lite/app.py", "tests/test_authz.py"}
    fresh = fresh_checkout(snapshot, tmp_path / "fresh")
    ok, err = apply_diff(fresh, diff)
    assert ok, err
    assert "require_owner(p.customer_id, customer)" in (fresh / "payments_lite/app.py").read_text()
    assert (fresh / "tests" / "test_authz.py").is_file()
    assert sha256_text(diff) == sha256_text(diff)


def test_apply_diff_rejects_paths_outside_root(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    evil = "diff --git a/../../etc/x b/../../etc/x\n--- a/../../etc/x\n+++ b/../../etc/x\n"
    with pytest.raises(PlatformError):
        apply_diff(root, evil)


def test_bad_diff_does_not_apply(snapshot, tmp_path):
    fresh = fresh_checkout(snapshot, tmp_path / "f")
    ok, err = apply_diff(
        fresh, "diff --git a/payments_lite/app.py b/payments_lite/app.py\n@@ -1,1 +1,1 @@\n-nope\n+yes\n"
    )
    assert not ok and err


# --------------------------------------------------------------------------- spec policy


def test_profile_network_combinations_are_enforced(snapshot):
    validate_spec(spec_for(snapshot))  # test-runner + none: fine
    with pytest.raises(PlatformError) as exc:
        validate_spec(spec_for(snapshot, network="target-only", scope_decision=ALLOWED, target_id="t"))
    assert exc.value.code is ErrorCode.SANDBOX_POLICY_VIOLATION


@pytest.mark.boundary
def test_target_network_requires_an_allowed_scope_decision(snapshot):
    base = dict(profile=SandboxProfile.CHECK_RUNNER, network="target-only", target_id="tgt")
    with pytest.raises(PlatformError) as exc:
        validate_spec(spec_for(snapshot, **base))
    assert exc.value.code is ErrorCode.SCOPE_DENIED
    with pytest.raises(PlatformError) as exc:
        validate_spec(spec_for(snapshot, **base, scope_decision=DENIED))
    assert exc.value.code is ErrorCode.SCOPE_DENIED
    validate_spec(spec_for(snapshot, **base, scope_decision=ALLOWED))


def test_extra_files_cannot_overwrite_the_entrypoint(snapshot):
    for name in ("entry.py", "harness.py", "../x.py", ".hidden"):
        with pytest.raises(PlatformError):
            validate_spec(spec_for(snapshot, extra_files={name: "x"}))


# --------------------------------------------------------------------------- local driver


def test_local_driver_is_disabled_unless_explicitly_allowed(monkeypatch):
    monkeypatch.delenv("SANDBOX_ALLOW_LOCAL_PROCESS", raising=False)
    with pytest.raises(PlatformError) as exc:
        LocalProcessDriver()
    assert exc.value.code is ErrorCode.SANDBOX_START_FAILED


def test_local_driver_runs_the_target_suite(snapshot, driver):
    res = driver.run(spec_for(snapshot))
    assert res.exit_code == 0 and not res.timed_out
    assert "passed" in res.stdout
    assert res.isolation_level.endswith("not-a-security-boundary")
    assert res.labels["assessment_id"] == "asm"


def test_local_driver_does_not_mutate_the_snapshot(snapshot, driver):
    before = tree_digest(snapshot.root)
    driver.run(spec_for(snapshot))
    assert tree_digest(snapshot.root) == before


@pytest.mark.boundary
def test_sandbox_without_network_cannot_connect(snapshot, driver):
    """SB-03 (dev driver): a no-network sandbox cannot open a TCP connection."""
    res = driver.run(spec_for(snapshot, mode="netprobe", args=["example.com", "80"]))
    payload = res.out_json("netprobe.json")
    assert payload is not None, res.stderr
    assert payload["connected"] is False
    assert "SANDBOX_POLICY_VIOLATION" in payload["error"] or "PermissionError" in payload["error"]


def test_sandbox_timeout_is_enforced(snapshot, driver, tmp_path):
    spec = spec_for(
        snapshot,
        extra_files={"test_slow.py": "import time\n\ndef test_slow():\n    time.sleep(30)\n"},
        args=["-q", ".sandbox/test_slow.py"],
        limits=SandboxLimits(timeout_s=2.0),
    )
    res = driver.run(spec)
    assert res.timed_out and res.exit_code is None
    assert res.duration_s < 10


def test_sandbox_collects_out_files(snapshot, driver):
    writer = (
        "import json, os\n\n"
        "def test_write():\n"
        "    with open(os.path.join(os.environ['SANDBOX_OUT'], 'result.json'), 'w') as fh:\n"
        "        json.dump({'ok': True}, fh)\n"
    )
    res = driver.run(spec_for(snapshot, extra_files={"test_w.py": writer}, args=["-q", ".sandbox/test_w.py"]))
    assert res.out_json("result.json") == {"ok": True}


def test_sandbox_env_is_scrubbed(snapshot, driver, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-never-be-visible")
    leaker = (
        "import json, os\n\n"
        "def test_env():\n"
        "    with open(os.path.join(os.environ['SANDBOX_OUT'], 'env.json'), 'w') as fh:\n"
        "        json.dump({'names': sorted(os.environ)}, fh)\n"
    )
    res = driver.run(spec_for(snapshot, extra_files={"test_e.py": leaker}, args=["-q", ".sandbox/test_e.py"]))
    payload = res.out_json("env.json")
    assert payload is not None, res.stderr
    names = payload["names"]
    assert "ANTHROPIC_API_KEY" not in names
    assert not any(n.endswith(("_KEY", "_TOKEN", "_SECRET")) for n in names), names


# --------------------------------------------------------------------------- docker driver


class FakeDocker:
    """Records docker argv instead of running it (no engine on dev machines)."""

    def __init__(self, ps_output: bytes = b"") -> None:
        self.calls: list[list[str]] = []
        self.ps_output = ps_output

    def __call__(self, argv, stdin, timeout):
        self.calls.append(argv)
        out = self.ps_output if argv[1:3] == ["ps", "-a"] else b""
        return subprocess.CompletedProcess(argv, 0, out, b"")


IMAGE = "ghcr.io/example/sandbox@sha256:" + "a" * 64


def test_docker_image_must_be_pinned_by_digest(monkeypatch):
    monkeypatch.delenv("SANDBOX_ALLOW_UNPINNED_IMAGE", raising=False)
    with pytest.raises(PlatformError) as exc:
        DockerSandboxDriver(image="python:3.12", runner=FakeDocker())
    assert exc.value.code is ErrorCode.SANDBOX_START_FAILED
    DockerSandboxDriver(image=IMAGE, runner=FakeDocker())


@pytest.mark.boundary
def test_docker_hardening_flags_present(snapshot):
    """SB-05: non-root, no capabilities, read-only rootfs, no socket, limits applied."""
    drv = DockerSandboxDriver(image=IMAGE, runner=FakeDocker())
    argv = drv.build_run_argv(spec_for(snapshot), "run1", None)
    flat = " ".join(argv)
    assert "--network none" in flat
    assert "--user 65534:65534" in flat
    assert "--cap-drop ALL" in flat
    assert "--security-opt no-new-privileges:true" in flat
    assert "--read-only" in flat
    assert "--pids-limit 256" in flat
    assert "--cpus 1.0" in flat
    assert "--memory" in flat
    assert "/var/run/docker.sock" not in flat
    assert " -v " not in flat and "--mount" not in flat, "no host mounts allowed"
    assert f"--label {LABEL_ROOT}.run_id=run1" in flat


@pytest.mark.boundary
def test_docker_target_only_network_is_internal_and_scope_gated(snapshot):
    drv = DockerSandboxDriver(image=IMAGE, runner=FakeDocker())
    spec = spec_for(
        snapshot,
        profile=SandboxProfile.CHECK_RUNNER,
        network="target-only",
        target_id="tgt",
        scope_decision=ALLOWED,
        mode="pytest",
        args=["-q"],
    )
    argv = drv.build_run_argv(spec, "run2", "net-run2")
    assert "--network" in argv and argv[argv.index("--network") + 1] == "net-run2"
    denied = spec_for(
        snapshot,
        profile=SandboxProfile.CHECK_RUNNER,
        network="target-only",
        target_id="tgt",
        scope_decision=DENIED,
    )
    with pytest.raises(PlatformError):
        validate_spec(denied)


def test_docker_reaper_removes_only_expired_containers():
    now = 1_000_000.0
    rows = (
        f"sbx-old\t{now - 1000}\t300\n"  # age 1000 > 2*300 -> reap
        f"sbx-young\t{now - 100}\t300\n"  # age 100 < 600 -> keep
        f"sbx-bad\tnot-a-number\t300\n"  # malformed -> keep
    ).encode()
    fake = FakeDocker(ps_output=rows)
    drv = DockerSandboxDriver(image=IMAGE, runner=fake)
    removed = drv.reap(now=now)
    assert removed == ["sbx-old"]
    assert any(c[1:3] == ["rm", "-f"] and c[-1] == "sbx-old" for c in fake.calls)
