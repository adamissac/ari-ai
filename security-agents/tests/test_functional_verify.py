"""Functional-defect Verify (Srihith's design 20261017T072519Z, Sai's inputs): the verdict
rule for the reproduction, and the deterministic path rebasing of reviewer patches."""

from __future__ import annotations

from pathlib import Path

import pytest

from security_agents.agents import verify as verify_agent
from security_agents.contracts import PlatformError
from security_agents.sandbox.workspace import SnapshotHandle, apply_diff, fresh_checkout
from security_agents.workflow import functional

TEST = "tests/generated/test_cr_bound.py"


def _evidence(**kw):
    base = dict(
        apply_facts={"applied": True, "files_touched": ["app.py", TEST], "out_of_scope": []},
        recheck_runs=[],
        test_runs=[
            {"selection": "added_tests", "passed": 1, "failing_tests": [], "sandbox_run_id": "sbx_a"},
            {"selection": "project_suite", "passed": 5, "failing_tests": [], "sandbox_run_id": "sbx_s"},
        ],
        baseline_failing=[],
        tests_added=[TEST],
        protected_tests=[],
        original_check_ref=None,
        original_check_params={},
        functional=True,
        reproduction_runs=[
            {"passed": 0, "failing_tests": [f"{TEST}::test_bound"], "sandbox_run_id": "sbx_r"}
        ],
    )
    return verify_agent.VerifyEvidence(**{**base, **kw})


def test_functional_accepts_only_a_reproduced_then_fixed_defect() -> None:
    verdict, checks, _ = verify_agent.compute_verdict(_evidence())
    assert verdict == "accepted" and all(c.passed for c in checks)

    not_reproduced = _evidence(
        reproduction_runs=[{"passed": 1, "failing_tests": [], "sandbox_run_id": "sbx_r"}]
    )
    verdict, _, reasons = verify_agent.compute_verdict(not_reproduced)
    assert verdict == "rejected" and any("did not fail unpatched" in r for r in reasons)

    verdict, _, reasons = verify_agent.compute_verdict(_evidence(reproduction_runs=[]))
    assert verdict == "rejected" and any("not run on the unpatched" in r for r in reasons)

    still_failing = _evidence(
        test_runs=[
            {"selection": "added_tests", "passed": 0, "failing_tests": [f"{TEST}::test_bound"]},
            {"selection": "project_suite", "passed": 5, "failing_tests": []},
        ]
    )
    assert verify_agent.compute_verdict(still_failing)[0] == "rejected"


def test_security_mode_unchanged_without_a_check() -> None:
    ev = _evidence(functional=False)
    verdict, _, reasons = verify_agent.compute_verdict(ev)
    assert verdict == "rejected" and any("no original check template" in r for r in reasons)


@pytest.fixture
def snapshot(tmp_path: Path) -> SnapshotHandle:
    src = tmp_path / "src"
    (src / "pkg").mkdir(parents=True)
    (src / "pkg" / "app.py").write_text("LIMIT = 1\n")
    (src / "tests").mkdir()
    return SnapshotHandle.from_directory(src, tmp_path / "snap", snapshot_id="snp_t", repo_id="rep_t")


def test_reviewer_paths_rebase_onto_the_snapshot_and_apply(snapshot, tmp_path) -> None:
    diff = (
        "diff --git a/target/pkg/app.py b/target/pkg/app.py\n"
        "--- a/target/pkg/app.py\n+++ b/target/pkg/app.py\n"
        "@@ -1 +1 @@\n-LIMIT = 1\n+LIMIT = 2\n"
    )
    prefix = functional.detect_prefix(diff, snapshot)
    assert prefix == "target/"
    code = functional.rebase_diff(diff, prefix)
    tests = functional.new_file_diff(
        [(functional.rebase_path(f"target/{TEST}", prefix), "def test_x():\n    assert True")]
    )
    root = fresh_checkout(snapshot, tmp_path / "fresh")
    ok, err = apply_diff(root, code + tests)
    assert ok, err
    assert (root / "pkg" / "app.py").read_text() == "LIMIT = 2\n"
    assert (root / TEST).read_text() == "def test_x():\n    assert True"  # byte for byte
    with pytest.raises(PlatformError):
        functional.rebase_path("elsewhere/x.py", prefix)
    with pytest.raises(PlatformError):
        functional.detect_prefix(diff.replace("pkg/app.py", "pkg/missing.py"), snapshot)
