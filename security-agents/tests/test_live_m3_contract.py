"""Contract for the live M3 assertion, exercised on real scripted seven-agent runs (no paid calls).

The first live run reached state=completed with Fortify failing SCHEMA_INVALID, and the old
assertions (every role ran, every role made a live turn, state=completed) passed it. These
tests pin that a failed Fortify can no longer satisfy the M3 check.
"""

from __future__ import annotations

import copy

from security_agents.agents import fortify as fortify_agent
from security_agents.contracts import AgentName
from security_agents.llm import FakeTurn

from . import fake_agents
from .live_m3 import SEVEN_ROLES, m3_failures
from .test_e2e_replay import build


def _old_live_assertions_pass(report: dict, *, require_live: bool) -> bool:
    """The assertions the live test used before this change, kept here only as evidence."""
    per_role = {role: [r for r in report["runs"] if r["agent"] == role] for role in SEVEN_ROLES}
    if any(not runs for runs in per_role.values()):
        return False
    if require_live and any(
        not any(r["provider_mode"] == "live" and r["llm_turns"] >= 1 for r in runs)
        for runs in per_role.values()
    ):
        return False
    return report["state"] == "completed"


def test_full_scripted_seven_agent_run_meets_every_m3_condition(intel, driver, library, tmp_path):
    report = build(intel, driver, library, tmp_path)[0].run().report()
    assert m3_failures(report, require_live=False) == []
    finding = next(f for f in report["findings"] if f["validation_outcome"] == "confirmed")
    assert finding["status"] == "hardened"
    assert finding["patch_candidates"] >= 1 and finding["patch_tests_added"]
    assert "accepted" in finding["verdicts"]


def test_failed_fortify_fails_m3_even_though_the_assessment_completes(intel, driver, library, tmp_path):
    submit = fortify_agent.SPEC.submit_tool_name()
    bad = {"recommendations": [], "future_hypotheses": [], "monitoring_hints": []}  # min_length=1 violated
    scripts = fake_agents.all_scripts(intel.snapshot.root)
    scripts[AgentName.FORTIFY] = [FakeTurn(tool_calls=[(submit, bad)]) for _ in range(6)]
    report = build(intel, driver, library, tmp_path, scripts=scripts)[0].run().report()

    fortify_runs = [r for r in report["runs"] if r["agent"] == "fortify"]
    assert fortify_runs[-1]["status"] == "failed" and fortify_runs[-1]["error_code"] == "SCHEMA_INVALID"
    assert fortify_runs[-1]["error_detail"], "the report now carries the exact validation failure"
    assert report["state"] == "completed", "the orchestrator still reports normally"
    assert _old_live_assertions_pass(report, require_live=False), "the old check would have passed this run"

    failures = m3_failures(report, require_live=False)
    assert any(f.startswith("2 completed") and "fortify" in f for f in failures)
    assert any(f.startswith("6 fortify") for f in failures)


def test_each_m3_condition_is_reported_separately(intel, driver, library, tmp_path):
    good = build(intel, driver, library, tmp_path)[0].run().report()

    def broken(mutate) -> list[str]:
        report = copy.deepcopy(good)
        mutate(report)
        return m3_failures(report, require_live=False)

    assert any(
        f.startswith("1 invoked")
        for f in broken(lambda r: r.update(runs=[x for x in r["runs"] if x["agent"] != "trace"]))
    )
    assert any(
        f.startswith("3 probe")
        for f in broken(lambda r: [f.update(validation_outcome="inconclusive") for f in r["findings"]])
    )
    assert any(
        f.startswith("4 patch")
        for f in broken(lambda r: [f.update(patch_candidates=0) for f in r["findings"]])
    )
    assert any(
        f.startswith("5 verify")
        for f in broken(lambda r: [f.update(verdicts=["rejected"]) for f in r["findings"]])
    )
    assert any(f.startswith("7 terminal") for f in broken(lambda r: r.update(state="failed")))
    # Scripted turns can never satisfy the live requirement.
    assert any(f.startswith("live:") for f in m3_failures(good, require_live=True))
