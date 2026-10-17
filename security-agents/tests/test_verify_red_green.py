"""Verify requires a regression test to reproduce the finding: Patch's added tests must FAIL on
the unpatched snapshot (platform-run) and pass after the patch. Passing on both proves nothing."""

from __future__ import annotations

import dataclasses

from security_agents.agents import verify as verify_agent

from .test_e2e_replay import build
from .test_verify_followups import ADDED, _ev

GREEN = [
    {"selection": "added_tests", "passed": 1, "failing_tests": [], "sandbox_run_id": "sbx_g"},
    {"selection": "project_suite", "passed": 5, "failing_tests": [], "sandbox_run_id": "sbx_s"},
]


def _with_unpatched(runs):
    return dataclasses.replace(_ev(GREEN), unpatched_added_runs=runs)


def _generated(checks):
    return next(c for c in checks if c.name.value == "generated_tests_pass")


def test_red_on_unpatched_and_green_after_is_accepted():
    ev = _with_unpatched(
        [
            {
                "passed": 0,
                "failing_tests": [f"{ADDED}::test_other_customer_is_refused"],
                "sandbox_run_id": "sbx_r",
            }
        ]
    )
    verdict, checks, _ = verify_agent.compute_verdict(ev)
    assert verdict == "accepted"
    assert "fail on the unpatched code" in _generated(checks).detail


def test_tests_that_already_pass_on_unpatched_code_are_rejected():
    ev = _with_unpatched([{"passed": 2, "failing_tests": [], "sandbox_run_id": "sbx_r"}])
    verdict, checks, reasons = verify_agent.compute_verdict(ev)
    assert verdict == "rejected"
    assert not _generated(checks).passed
    assert any("already pass on the unpatched code" in r for r in reasons)


def test_unpatched_run_that_could_not_execute_fails_closed():
    for runs in ([], [{"error": "SANDBOX_ERROR", "detail": "boom"}]):
        verdict, _, reasons = verify_agent.compute_verdict(_with_unpatched(runs))
        assert verdict == "rejected"
        assert any("could not be run on the unpatched code" in r for r in reasons)


def test_an_unrelated_failure_on_unpatched_does_not_count_as_red():
    ev = _with_unpatched(
        [{"passed": 1, "failing_tests": ["tests/test_api.py::test_old_flake"], "sandbox_run_id": "sbx_r"}]
    )
    assert verify_agent.compute_verdict(ev)[0] == "rejected"


def test_callers_that_do_not_collect_the_unpatched_run_keep_the_previous_rule():
    assert verify_agent.compute_verdict(_ev(GREEN))[0] == "accepted"


def test_orchestrator_runs_added_tests_on_the_unpatched_snapshot(intel, driver, library, tmp_path):
    """Real scripted seven-agent run: the platform executes Patch's test on unpatched code, sees it
    fail, and Verify records that red/green evidence in its accepted verdict."""
    orch, _ = build(intel, driver, library, tmp_path)
    result = orch.run()
    finding = next(f for f in result.findings if f.verifications)
    verification = finding.verifications[-1]
    assert verification.verdict == "accepted"
    detail = next(c.detail for c in verification.checks if c.name.value == "generated_tests_pass")
    assert "fail on the unpatched code" in detail
    assert "tests.added_on_unpatched" in [e.action for e in result.audit]
