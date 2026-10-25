"""Follow-ups from the #71/#73 reviews: Verify cannot be masked by a later run, and the
no-snapshot reviewer fallback uses a documented synthetic ref (never a random id)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from security_agents.agents import verify as verify_agent

ADDED = "tests/test_new_case.py"


def _ev(test_runs: list[dict[str, Any]]) -> verify_agent.VerifyEvidence:
    patch_id = "pat_test"
    return verify_agent.VerifyEvidence(
        apply_facts={
            "applied": True,
            "patch_id": patch_id,
            "files_touched": ["app.py", ADDED],
            "out_of_scope": [],
        },
        recheck_runs=[
            {"template_ref": "t@1", "matches_expectation": True, "sandbox_run_id": "sbx_c", "parameters": {}}
        ],
        test_runs=[{**run, "patch_id": run.get("patch_id", patch_id)} for run in test_runs],
        baseline_failing=[],
        tests_added=[ADDED],
        protected_tests=[],
        original_check_ref="t@1",
        original_check_params={},
    )


def test_a_later_run_cannot_mask_an_added_test_failure() -> None:
    masked = _ev(
        [
            {
                "selection": "added_tests",
                "passed": 0,
                "failing_tests": [f"{ADDED}::test_x"],
                "pytest_args": ["-q", ADDED],
                "workspace_role": "patched",
            },
            {"selection": "project_suite", "passed": 5, "failing_tests": []},
        ]
    )
    verdict, _, reasons = verify_agent.compute_verdict(masked)
    assert verdict == "rejected" and any("added tests failing" in r for r in reasons)
    clean = _ev(
        [
            {
                "selection": "added_tests",
                "passed": 1,
                "failing_tests": [],
                "pytest_args": ["-q", ADDED],
                "workspace_role": "patched",
            },
            {"selection": "project_suite", "passed": 5, "failing_tests": []},
        ]
    )
    assert verify_agent.compute_verdict(clean)[0] == "accepted"


@pytest.mark.parametrize(
    "added_run",
    [
        None,
        {
            "selection": "added_tests",
            "passed": 0,
            "failing_tests": [f"{ADDED}::test_x"],
            "pytest_args": ["-q", ADDED],
            "workspace_role": "patched",
        },
        {
            "selection": "added_tests",
            "passed": 1,
            "failing_tests": [],
            "pytest_args": ["-q", "tests/test_other.py"],
            "workspace_role": "patched",
        },
        {
            "selection": "added_tests",
            "passed": 1,
            "failing_tests": [],
            "pytest_args": ["-q", ADDED],
            "workspace_role": "unpatched",
        },
    ],
    ids=["absent", "failing", "wrong-files-selected", "unpatched"],
)
def test_project_suite_does_not_prove_generated_tests_pass(
    added_run: dict[str, Any] | None,
) -> None:
    runs: list[dict[str, Any]] = [{"selection": "project_suite", "passed": 5, "failing_tests": []}]
    if added_run is not None:
        runs.append(added_run)

    _, checks, _ = verify_agent.compute_verdict(_ev(runs))

    assert not next(c for c in checks if c.name.value == "generated_tests_pass").passed


def test_pre_apply_project_suite_does_not_prove_applied_patch() -> None:
    runs = [
        {
            "selection": "project_suite",
            "passed": 5,
            "failing_tests": [],
            "patch_id": None,
        },
        {
            "selection": "added_tests",
            "passed": 1,
            "failing_tests": [],
            "pytest_args": ["-q", ADDED],
            "workspace_role": "patched",
            "patch_id": "pat_test",
        },
    ]
    verdict, checks, _ = verify_agent.compute_verdict(_ev(runs))

    assert verdict == "rejected"
    assert not next(c for c in checks if c.name.value == "functional_suite_passes").passed


def test_review_without_snapshot_uses_a_documented_synthetic_ref() -> None:
    from shared.tenancy import Budget

    from security_agents.host_adapter import _review_without_snapshot

    sha = "c" * 40
    a = SimpleNamespace(
        id="asm_12345678", project_id="prj_12345678", commit_sha=sha, snapshot_id=None, budget=Budget()
    )
    seen: list = []

    class Api:
        def resolve_repo(self, repo_id, commit_sha):
            return "src"

        def review_full(self, host, request, source):
            seen.append(request.snapshot_ref)

    host = SimpleNamespace(assessment=a, repo_id="rep_12345678")
    _review_without_snapshot(host, None, Api())
    _review_without_snapshot(host, None, Api())
    assert seen[0].snapshot_id == f"snp_unindexed-{sha}"
    assert seen[0].index_version == "unindexed-checkout"
    assert seen[1].snapshot_id == seen[0].snapshot_id


def test_functional_verify_is_labelled_none_not_a_model_provider() -> None:
    """Deterministic functional Verify must not claim live/fake provider provenance (#84/#83 leftover)."""
    import inspect

    from security_agents.host_adapter import _verify_functional_patch

    src = inspect.getsource(_verify_functional_patch)
    assert 'provider_mode="none"' in src
    assert 'model_id="deterministic:functional-verify"' in src
    start = src.split("start_agent_run", 1)[1]
    assert "provider_mode=provider_mode" not in start.split(")", 1)[0]
