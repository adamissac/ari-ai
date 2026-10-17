"""End-to-end: Scout -> Probe -> Trace -> Diagnose -> Patch -> Verify -> Fortify.

Deterministic (fake provider), but everything else is real: real tool
authorization, real sandboxed check and test execution, a real diff written to
a real worktree, and an independent Verify run that re-checks the patched code
in a fresh checkout. Labelled `fake` provider mode throughout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from security_agents.contracts import AgentName, Approval, Budget, ValidationOutcome
from security_agents.llm import FakeLLM, ProviderGateway
from security_agents.workflow import AssessmentState, FindingRecord, Orchestrator, OrchestratorConfig

from . import fake_agents
from .conftest import TARGET_ID, live_scope

EXPECTED_AGENT_ORDER = ["scout", "probe", "trace", "diagnose", "patch", "verify", "fortify"]


def build(intel, driver, library, tmp_path: Path, *, scripts=None, approve=True, **patch_kw):
    scripts = scripts or fake_agents.all_scripts(intel.snapshot.root, **patch_kw)
    gateway = ProviderGateway(FakeLLM(scripts), default_model="claude-opus-5-5")

    def approver(finding: FindingRecord) -> Approval | None:
        if not approve or finding.plan is None:
            return None
        return Approval(
            project_id="prj_test", subject_type="remediation", subject_id=finding.plan.id,
            decision="approved", decided_by="usr_human_reviewer", reason="plan reviewed in test",
        )

    config = OrchestratorConfig(
        assessment_id="asm_e2e",
        project_id="prj_test",
        org_id="org_test",
        scope=live_scope(),
        target_id=TARGET_ID,
        requested_by="usr_requester",
        budget=Budget(max_tokens=2_000_000, max_usd=50.0, max_wall_clock_s=900.0),
        max_hypotheses_to_validate=2,
    )
    return Orchestrator(
        config, intel=intel, gateway=gateway, driver=driver, library=library,
        workdir=tmp_path / "work", approve_remediation=approver,
    ), gateway


@pytest.fixture(scope="module")
def _e2e_cache() -> dict:
    return {}


@pytest.fixture
def result(intel, driver, library, tmp_path):
    orch, gateway = build(intel, driver, library, tmp_path)
    res = orch.run()
    return res, gateway


def test_assessment_completes_through_every_state(result):
    res, _ = result
    assert res.state is AssessmentState.COMPLETED, res.error_detail
    assert res.state_log.states() == [
        "scope_check", "indexing", "functional_review", "recon", "validation", "analysis",
        "diagnosis", "awaiting_approval", "remediation", "hardening", "reporting", "completed",
    ]


def test_all_seven_agents_ran_as_separate_runs(result):
    res, _ = result
    order = [r.agent.value for r in res.runs]
    assert order == EXPECTED_AGENT_ORDER, order
    assert len({r.id for r in res.runs}) == 7, "each agent step is its own AgentRun"
    assert all(r.status == "succeeded" for r in res.runs), [
        (r.agent.value, r.error_code) for r in res.runs if r.status != "succeeded"
    ]


def test_each_run_has_distinct_role_identity_and_tool_history(result):
    res, gateway = result
    by_agent = {r.agent.value: r for r in res.runs}
    assert set(by_agent) == set(EXPECTED_AGENT_ORDER)
    # distinct system prompts per role, from the provider's own request log
    systems = {c.agent.value: c.system for c in gateway.provider.calls}
    assert len(set(systems.values())) == 7
    # distinct tool histories
    histories = {rec.agent.value: tuple(rec.tool_names()) for rec in res.records}
    assert len(set(histories.values())) == 7, histories
    assert "checks.run_template" in histories["probe"]
    assert "worktree.write_file" in histories["patch"]
    assert "patch.apply_fresh" in histories["verify"]
    assert "checks.run_template" not in histories["scout"]
    assert "worktree.write_file" not in histories["verify"]


def test_every_agent_made_at_least_one_model_request_and_one_tool_call(result):
    res, gateway = result
    per_agent: dict[str, int] = {}
    for call in gateway.provider.calls:
        per_agent[call.agent.value] = per_agent.get(call.agent.value, 0) + 1
    assert set(per_agent) == set(EXPECTED_AGENT_ORDER)
    assert all(n >= 2 for n in per_agent.values()), per_agent
    for rec in res.records:
        assert rec.tool_invocations, f"{rec.agent.value} made no tool call"


def test_scout_hypothesis_cites_the_real_handler(result):
    res, _ = result
    finding = res.findings[0]
    span = finding.hypothesis.cited_spans[0]
    assert span.path == "payments_lite/app.py"
    assert finding.hypothesis.weakness_class == "CWE-639"
    assert "exp_tenant_isolation_payments" in finding.hypothesis.expectation_ids


def test_probe_confirmed_the_planted_weakness_with_executed_evidence(result):
    res, _ = result
    finding = res.findings[0]
    assert finding.validation is not None
    assert finding.validation.outcome is ValidationOutcome.CONFIRMED
    assert finding.validation.check_template_id == "access_control.ownership"
    assert finding.validation.sandbox_run_id
    assert finding.validation.observations["outcome_source"] == "executed_check"
    assert finding.validation.evidence[0].provenance == "check_run"


def test_trace_severity_is_computed_from_cited_factors(result):
    res, _ = result
    finding = res.findings[0]
    assert finding.severity is not None
    assert finding.severity.level.value == "high"
    assert finding.severity.factors.data_sensitivity == "financial"
    assert finding.severity.factors.verified_path is True
    verified = [s for s in finding.attack_path.steps if s.verified]
    assert verified and all(s.evidence for s in verified)


def test_diagnose_plan_bounds_the_patch(result):
    res, _ = result
    finding = res.findings[0]
    assert finding.root_cause is not None and finding.plan is not None
    assert finding.root_cause.cause_class.value == "missing_check"
    assert finding.plan.files_expected == ["payments_lite/app.py"]
    assert finding.plan.test_plan.must_pass_after


def test_patch_produced_a_real_minimal_diff_with_a_new_test(result, tmp_path):
    res, _ = result
    finding = res.findings[0]
    assert finding.candidates, finding.notes
    candidate = finding.candidates[-1]
    assert set(candidate.files_changed) == {"payments_lite/app.py", "tests/test_authz_regression.py"}
    assert candidate.tests_added == ["tests/test_authz_regression.py"]
    diff = (tmp_path / "work" / f"patch-{finding.finding_id}-1.diff").read_text()
    assert "get_payment_for_customer(payment_id, customer.id)" in diff
    assert diff.count("diff --git") == 2
    assert candidate.diff_sha256


def test_verify_accepted_on_executed_evidence(result):
    res, _ = result
    finding = res.findings[0]
    assert finding.verifications, finding.notes
    verification = finding.verifications[-1]
    assert verification.verdict == "accepted", verification.reasons
    passed = {c.name.value: c.passed for c in verification.checks}
    assert all(passed.values()), passed
    assert len(verification.checks) == 5
    assert verification.sandbox_run_ids


def test_verify_ran_in_its_own_sandboxes_separate_from_patch(result):
    res, _ = result
    finding = res.findings[0]
    verify_ids = set(finding.verifications[-1].sandbox_run_ids)
    patch_record = next(r for r in res.records if r.agent is AgentName.PATCH)
    patch_ids = {
        inv.summary.get("sandbox_run_id")
        for inv in patch_record.tool_invocations
        if inv.summary.get("sandbox_run_id")
    }
    assert verify_ids and not (verify_ids & patch_ids)


def test_verify_received_no_patch_transcript(result):
    """Independence: nothing from Patch's conversation reaches Verify's prompt."""
    res, gateway = result
    patch_calls = [c for c in gateway.provider.calls if c.agent is AgentName.PATCH]
    verify_calls = [c for c in gateway.provider.calls if c.agent is AgentName.VERIFY]
    patch_explanation = "Applying the scoped lookup"
    verify_text = "\n".join(str(m) for c in verify_calls for m in c.messages)
    assert patch_explanation in "\n".join(str(m) for c in patch_calls for m in c.messages)
    assert patch_explanation not in verify_text
    assert "Replaced the unscoped payment lookup" not in verify_text


def test_fortify_promoted_a_regression_test(result):
    res, _ = result
    finding = res.findings[0]
    assert finding.status == "hardened"
    assert len(finding.regression_tests) >= 1
    assert finding.regression_tests[0].test_path == "tests/test_authz_regression.py"
    assert finding.recommendations
    assert finding.monitoring_hints


def test_typed_handoff_chain_is_linked_by_ids(result):
    res, _ = result
    finding = res.findings[0]
    assert finding.validation.hypothesis_id == finding.hypothesis.id
    assert finding.attack_path.finding_id == finding.finding_id
    assert finding.root_cause.finding_id == finding.finding_id
    assert finding.plan.finding_id == finding.finding_id
    assert finding.candidates[-1].finding_id == finding.finding_id
    assert finding.verifications[-1].patch_id == finding.candidates[-1].id
    assert finding.regression_tests[0].finding_id == finding.finding_id


def test_audit_chain_is_hash_linked_and_covers_the_gates(result):
    res, _ = result
    actions = [e.action for e in res.audit]
    for expected in (
        "scope.checked", "agent.step", "finding.hypothesis", "finding.validation",
        "finding.severity", "finding.diagnosed", "approval.granted", "patch.candidate",
        "finding.verification", "finding.hardened", "assessment.completed",
    ):
        assert expected in actions, expected
    prev = "0" * 64
    for event in res.audit:
        assert event.prev_hash == prev
        prev = event.hash
    assert len({e.hash for e in res.audit}) == len(res.audit)


def test_report_is_honest_about_provider_mode(result):
    res, _ = result
    report = res.report()
    assert report["provider_modes"] == ["fake"]
    assert report["state"] == "completed"
    assert sorted(report["agents_executed"]) == sorted(EXPECTED_AGENT_ORDER)
    assert report["usage"]["sandbox_seconds"] > 0
    assert report["findings"][0]["status"] == "hardened"
    assert report["findings"][0]["verdicts"] == ["accepted"]


def test_usage_is_accounted_across_the_assessment(result):
    res, _ = result
    assert res.usage.total_tokens == sum(r.usage.total_tokens for r in res.runs)
    assert res.usage.usd > 0


# --------------------------------------------------------------------------- bad patches


@pytest.mark.boundary
def test_verify_rejects_a_patch_that_weakens_an_existing_test(intel, driver, library, tmp_path):
    """SB-09: a diff that edits a test encoding a confirmed expectation is rejected."""
    orch, _ = build(intel, driver, library, tmp_path, weaken_tests=True)
    res = orch.run()
    finding = res.findings[0]
    assert finding.verifications, finding.notes
    first = finding.verifications[0]
    assert first.verdict == "rejected"
    tampering = next(c for c in first.checks if c.name.value == "no_test_tampering")
    assert not tampering.passed
    assert any("test_payments.py" in r for r in first.reasons)
    assert finding.status in ("patch_rejected", "unresolved")


@pytest.mark.boundary
def test_verify_rejects_a_patch_that_changes_files_outside_the_plan(intel, driver, library, tmp_path):
    orch, _ = build(intel, driver, library, tmp_path, out_of_scope=True)
    res = orch.run()
    finding = res.findings[0]
    assert finding.verifications
    scope_check = next(c for c in finding.verifications[0].checks if c.name.value == "diff_scope_ok")
    assert not scope_check.passed
    assert "payments_lite/store.py" in scope_check.detail


@pytest.mark.boundary
def test_rejected_patch_is_retried_at_most_twice(intel, driver, library, tmp_path):
    orch, _ = build(intel, driver, library, tmp_path, weaken_tests=True)
    res = orch.run()
    patch_runs = [r for r in res.runs if r.agent is AgentName.PATCH]
    verify_runs = [r for r in res.runs if r.agent is AgentName.VERIFY]
    assert len(patch_runs) == 2, [r.attempt for r in patch_runs]
    assert len(verify_runs) == 2
    assert [r.attempt for r in patch_runs] == [1, 2]
    assert res.findings[0].status == "patch_rejected"


def test_patch_cannot_write_outside_the_plan(intel, driver, library, tmp_path):
    """The worktree refuses a path the approved plan does not cover."""
    from security_agents.tools import PatchWorktree

    worktree = PatchWorktree.create(intel, tmp_path / "wt", ["payments_lite/app.py"])
    denied = worktree.write_file("payments_lite/store.py", "x = 1\n")
    assert denied["error"] == "PATH_NOT_ALLOWED"
    assert not (worktree.root / "payments_lite" / "store.py").read_text().startswith("x = 1")
    allowed = worktree.write_file("tests/test_new_case.py", "def test_x():\n    assert True\n")
    assert allowed["action"] == "created"


# --------------------------------------------------------------------------- gates


def test_declined_remediation_stops_before_patching(intel, driver, library, tmp_path):
    orch, _ = build(intel, driver, library, tmp_path, approve=False)
    res = orch.run()
    assert res.state is AssessmentState.COMPLETED
    assert [r.agent.value for r in res.runs] == ["scout", "probe", "trace", "diagnose"]
    finding = res.findings[0]
    assert finding.status == "diagnosed"
    assert not finding.candidates
    assert "approval.absent" in [e.action for e in res.audit]


def test_agent_approval_is_not_accepted(intel, driver, library, tmp_path):
    """An approval that is not a human decision is ignored (docs/15 §7)."""
    scripts = fake_agents.all_scripts(intel.snapshot.root)
    gateway = ProviderGateway(FakeLLM(scripts))

    def agent_approver(finding: FindingRecord) -> Approval | None:
        return Approval(
            project_id="prj_test", subject_type="remediation",
            subject_id=finding.plan.id if finding.plan else "x",
            decision="approved", decided_by="agent:patch",
        )

    config = OrchestratorConfig(
        assessment_id="asm_gate", project_id="prj_test", org_id="org_test", scope=live_scope(),
        target_id=TARGET_ID, requested_by="usr_requester",
    )
    res = Orchestrator(
        config, intel=intel, gateway=gateway, driver=driver, library=library,
        workdir=tmp_path / "w", approve_remediation=agent_approver,
    ).run()
    assert not any(r.agent is AgentName.PATCH for r in res.runs)
    assert "approval.invalid_actor" in [e.action for e in res.audit]


def test_approval_for_a_different_plan_is_ignored(intel, driver, library, tmp_path):
    scripts = fake_agents.all_scripts(intel.snapshot.root)
    gateway = ProviderGateway(FakeLLM(scripts))

    def wrong_approver(finding: FindingRecord) -> Approval | None:
        return Approval(
            project_id="prj_test", subject_type="remediation", subject_id="rmp_someone_else",
            decision="approved", decided_by="usr_human",
        )

    config = OrchestratorConfig(
        assessment_id="asm_gate2", project_id="prj_test", org_id="org_test", scope=live_scope(),
        target_id=TARGET_ID, requested_by="usr_requester",
    )
    res = Orchestrator(
        config, intel=intel, gateway=gateway, driver=driver, library=library,
        workdir=tmp_path / "w", approve_remediation=wrong_approver,
    ).run()
    assert not any(r.agent is AgentName.PATCH for r in res.runs)
    assert "approval.mismatch" in [e.action for e in res.audit]
