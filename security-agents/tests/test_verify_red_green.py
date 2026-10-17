"""Verify requires a regression test to reproduce the finding: Patch's added tests must FAIL on
the unpatched snapshot in a clean pytest run (platform-run) and pass after the patch. Same
reproduction predicate as the functional path (issue #252)."""

from __future__ import annotations

import dataclasses

import pytest

from security_agents.agents import verify as verify_agent
from security_agents.host_adapter import _functional_reproduced

from .test_e2e_replay import build
from .test_verify_followups import ADDED, _ev

GREEN = [
    {"selection": "added_tests", "passed": 1, "failing_tests": [], "sandbox_run_id": "sbx_g"},
    {"selection": "project_suite", "passed": 5, "failing_tests": [], "sandbox_run_id": "sbx_s"},
]
RED = {
    "sandbox_run_id": "sbx_r",
    "exit_code": 1,
    "timed_out": False,
    "passed": 1,
    "failed": 1,
    "errors": 0,
    "failing_tests": [f"{ADDED}::test_other_customer_is_refused"],
    "failing_truncated": False,
}


def _with_unpatched(runs):
    return dataclasses.replace(_ev(GREEN), unpatched_added_runs=runs)


def _generated(checks):
    return next(c for c in checks if c.name.value == "generated_tests_pass")


def _reasons(run):
    verdict, _, reasons = verify_agent.compute_verdict(_with_unpatched([run]))
    return verdict, " ".join(reasons)


def test_clean_red_on_unpatched_and_green_after_is_accepted():
    verdict, checks, _ = verify_agent.compute_verdict(_with_unpatched([RED]))
    assert verdict == "accepted"
    assert "fail on the unpatched code" in _generated(checks).detail


def test_tests_that_already_pass_on_unpatched_code_are_rejected():
    verdict, why = _reasons({**RED, "exit_code": 0, "failed": 0, "passed": 2, "failing_tests": []})
    assert verdict == "rejected" and "already pass on the unpatched code" in why


@pytest.mark.parametrize(
    ("change", "phrase"),
    [
        ({"errors": 1, "exit_code": 2, "failed": 0, "failing_tests": []}, "collection/setup errors"),
        ({"errors": 1}, "collection/setup errors"),  # partial red with a collection error is not proof
        ({"timed_out": True}, "timed out"),
        ({"exit_code": 2}, "exited 2"),
        ({"exit_code": 5, "failed": 0, "failing_tests": []}, "exited 5"),
        ({"failing_truncated": True}, "truncated"),
        ({"failed": 3}, "truncated"),  # more failures reported than listed
        ({"error": "SANDBOX_ERROR"}, "failed to execute"),
    ],
)
def test_unclean_unpatched_runs_are_unproven_not_mislabeled(change, phrase):
    verdict, why = _reasons({**RED, **change})
    assert verdict == "rejected"
    assert phrase in why
    assert "already pass" not in why  # a collection error must never read as "already passes"


def test_unpatched_run_that_could_not_execute_fails_closed():
    verdict, _, reasons = verify_agent.compute_verdict(_with_unpatched([]))
    assert verdict == "rejected" and any("could not be run on the unpatched code" in r for r in reasons)


def test_every_added_test_file_must_fail_on_unpatched():
    two = dataclasses.replace(
        _ev(GREEN), tests_added=[ADDED, "tests/test_second.py"], unpatched_added_runs=[RED]
    )
    verdict, _, reasons = verify_agent.compute_verdict(two)
    assert verdict == "rejected" and any("not every added test file fails" in r for r in reasons)


def test_an_unrelated_failure_on_unpatched_does_not_count_as_red():
    verdict, why = _reasons({**RED, "failing_tests": ["tests/test_api.py::test_old_flake"]})
    assert verdict == "rejected" and "already pass on the unpatched code" in why


def test_security_and_functional_paths_share_one_predicate():
    assert verify_agent.clean_reproduction(RED, [ADDED]) is True
    for bad in (
        {**RED, "errors": 1},
        {**RED, "timed_out": True},
        {**RED, "exit_code": 2},
        {**RED, "failing_truncated": True},
    ):
        assert verify_agent.clean_reproduction(bad, [ADDED]) is False
        assert _functional_reproduced(bad, [ADDED]) is False
    assert _functional_reproduced(RED, [ADDED]) is True


def test_callers_that_do_not_collect_the_unpatched_run_keep_the_previous_rule():
    assert verify_agent.compute_verdict(_ev(GREEN))[0] == "accepted"


def test_orchestrator_runs_added_tests_on_the_unpatched_snapshot(intel, driver, library, tmp_path):
    """Real scripted seven-agent run: the platform executes Patch's test on unpatched code, sees a
    clean failing run, and Verify records that red/green evidence in its accepted verdict."""
    orch, _ = build(intel, driver, library, tmp_path)
    result = orch.run()
    finding = next(f for f in result.findings if f.verifications)
    verification = finding.verifications[-1]
    assert verification.verdict == "accepted"
    detail = next(c.detail for c in verification.checks if c.name.value == "generated_tests_pass")
    assert "fail on the unpatched code" in detail
    assert "tests.added_on_unpatched" in [e.action for e in result.audit]
