"""End-to-end: Scout -> Probe -> Trace -> Diagnose -> Patch -> Verify -> Fortify.

Deterministic (fake provider), but everything else is real: real tool
authorization, real sandboxed check and test execution, a real diff written to
a real worktree, and an independent Verify run that re-checks the patched code
in a fresh checkout. Labelled `fake` provider mode throughout.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from security_agents.checks.library import CheckLibrary
from security_agents.contracts import AgentName, Approval, Budget, ValidationOutcome
from security_agents.intel import LocalIntel, load_expectations
from security_agents.llm import FakeLLM, ProviderGateway
from security_agents.sandbox.driver import LocalProcessDriver
from security_agents.sandbox.workspace import SnapshotHandle
from security_agents.workflow import AssessmentState, FindingRecord, Orchestrator, OrchestratorConfig
from security_agents.workflow.states import MAX_PATCH_ATTEMPTS

from . import fake_agents
from .conftest import LABELS, TARGET_ID, live_scope

EXPECTED_AGENT_ORDER = ["scout", "probe", "trace", "diagnose", "patch", "verify", "fortify"]


def assert_agent_order(order: list[str]) -> None:
    """Scout then Probe; Diagnose runs alongside Trace, Fortify alongside Patch -> Verify."""
    assert order[:2] == EXPECTED_AGENT_ORDER[:2], order
    assert sorted(order[2:4]) == ["diagnose", "trace"], order
    rest = order[4:]
    assert sorted(rest) == sorted(EXPECTED_AGENT_ORDER[4:]), order
    assert rest.index("patch") < rest.index("verify"), order


def build(intel, driver, library, tmp_path: Path, *, scripts=None, approve=True, **patch_kw):
    scripts = scripts or fake_agents.all_scripts(intel.snapshot.root, **patch_kw)
    gateway = ProviderGateway(FakeLLM(scripts), default_model="claude-opus-5-5")

    def approver(finding: FindingRecord) -> Approval | None:
        if not approve or finding.plan is None:
            return None
        return Approval(
            project_id="prj_test",
            subject_type="remediation",
            subject_id=finding.plan.id,
            decision="approved",
            decided_by="usr_human_reviewer",
            reason="plan reviewed in test",
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
        config,
        intel=intel,
        gateway=gateway,
        driver=driver,
        library=library,
        workdir=tmp_path / "work",
        approve_remediation=approver,
    ), gateway


def _variant_intel(
    intel: LocalIntel,
    tmp_path: Path,
    *,
    recipe_changes: dict[str, object] | None = None,
) -> LocalIntel:
    staging = tmp_path / "variant-staging"
    shutil.copytree(intel.snapshot.root, staging, symlinks=True)
    for current, dirs, files in os.walk(staging, followlinks=False):
        directory = Path(current)
        directory.chmod(directory.stat().st_mode | 0o700)
        for name in dirs:
            path = directory / name
            if not path.is_symlink():
                path.chmod(path.stat().st_mode | 0o700)
        for name in files:
            path = directory / name
            if not path.is_symlink():
                path.chmod(path.stat().st_mode | 0o600)

    recipe_path = staging / "build_recipe.json"
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    recipe.update(recipe_changes or {})
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")

    snapshot = SnapshotHandle.from_directory(
        staging,
        tmp_path / "variant-snapshot",
        snapshot_id=f"{intel.snapshot.snapshot_id}-variant",
        repo_id=intel.snapshot.repo_id,
    )
    return LocalIntel(
        snapshot,
        expectations=load_expectations(
            LABELS,
            snapshot_id=snapshot.snapshot_id,
            commit_sha=snapshot.commit_sha,
            strip_prefix="target/",
        ),
    )


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
        "scope_check",
        "indexing",
        "functional_review",
        "recon",
        "validation",
        "analysis",
        "diagnosis",
        "awaiting_approval",
        "remediation",
        "hardening",
        "reporting",
        "completed",
    ]


def test_all_seven_agents_ran_as_separate_runs(result):
    res, _ = result
    order = [r.agent.value for r in res.runs]
    assert_agent_order(order)
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
    assert "exp_owner_only" in finding.hypothesis.expectation_ids


def test_probe_confirmed_the_planted_weakness_with_executed_evidence(result):
    res, _ = result
    finding = res.findings[0]
    assert finding.validation is not None
    assert finding.validation.outcome is ValidationOutcome.CONFIRMED
    assert finding.validation.check_template_id == "access_control.ownership"
    assert finding.validation.sandbox_run_id
    assert finding.validation.observations["outcome_source"] == "executed_check"
    assert finding.validation.evidence[0].provenance == "check_run"


def test_trace_severity_is_computed_by_the_platform_from_cvss_metrics(result):
    res, _ = result
    finding = res.findings[0]
    severity = finding.severity
    assert severity is not None
    assert severity.cvss_vector == "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"
    assert severity.cvss_base_score == 6.5
    assert severity.cvss_rating == "medium"
    assert severity.level.value == "medium"
    assert severity.score_kind.startswith("CVSS v3.1 base score only")
    assert severity.level_source.startswith("derived from the CVSS v3.1 qualitative rating")
    assert severity.factors.data_sensitivity == "financial"
    assert severity.factors.verified_path is True
    statuses = {e.metric: e.status for e in severity.metric_evidence}
    assert statuses["S"] == "unverified" and statuses["A"] == "unverified"
    assert statuses["C"] == "cited" and statuses["AV"] == "cited"
    verified = [s for s in finding.attack_path.steps if s.verified]
    assert verified and all(s.evidence for s in verified)


def test_base_score_differs_from_the_labelled_business_severity(result):
    res, _ = result
    assert res.findings[0].severity.cvss_rating == "medium"


def test_attack_path_records_no_applicable_technique_honestly(result):
    res, _ = result
    steps = res.findings[0].attack_path.steps
    assert all(step.attack_technique is None for step in steps)
    assert all(step.attack_label == "no applicable technique" for step in steps)


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
    assert "require_owner(p.customer_id, customer)" in diff
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
        "scope.checked",
        "agent.step",
        "finding.hypothesis",
        "finding.validation",
        "finding.severity",
        "finding.diagnosed",
        "approval.granted",
        "patch.candidate",
        "finding.verification",
        "finding.hardened",
        "assessment.completed",
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
def test_worktree_refuses_a_patch_attempt_that_weakens_an_existing_test(intel, driver, library, tmp_path):
    """First line of defence: the write is refused, so no weakened test reaches the diff."""
    orch, _ = build(intel, driver, library, tmp_path, weaken_tests=True)
    res = orch.run()
    finding = res.findings[0]
    patch_record = next(r for r in res.records if r.agent is AgentName.PATCH)
    refused = [
        inv
        for inv in patch_record.tool_invocations
        if inv.name == "worktree.write_file" and inv.error_code == "PATH_NOT_ALLOWED"
    ]
    assert refused, [(i.name, i.error_code) for i in patch_record.tool_invocations]
    candidate = finding.candidates[-1]
    assert "tests/test_payments.py" not in candidate.files_changed
    diff = (tmp_path / "work" / f"patch-{finding.finding_id}-1.diff").read_text()
    assert "tests/test_payments.py" not in diff


@pytest.mark.boundary
def test_worktree_refuses_a_patch_attempt_outside_the_plan(intel, driver, library, tmp_path):
    orch, _ = build(intel, driver, library, tmp_path, out_of_scope=True)
    res = orch.run()
    finding = res.findings[0]
    patch_record = next(r for r in res.records if r.agent is AgentName.PATCH)
    refused = [
        inv
        for inv in patch_record.tool_invocations
        if inv.name == "worktree.write_file" and inv.error_code == "PATH_NOT_ALLOWED"
    ]
    assert refused
    assert "payments_lite/store.py" not in finding.candidates[-1].files_changed


@pytest.mark.boundary
def test_ineffective_in_scope_patch_is_rejected_and_retried_then_unresolved(intel, driver, library, tmp_path):
    """Verify rejects a patch that does not fix the finding; the loop retries once."""
    orch, _ = build(intel, driver, library, tmp_path, ineffective=True)
    res = orch.run()
    patch_runs = [r for r in res.runs if r.agent is AgentName.PATCH]
    verify_runs = [r for r in res.runs if r.agent is AgentName.VERIFY]
    assert [r.attempt for r in patch_runs] == list(range(1, MAX_PATCH_ATTEMPTS + 1)), [
        r.attempt for r in patch_runs
    ]
    assert len(verify_runs) == MAX_PATCH_ATTEMPTS
    finding = res.findings[0]
    assert finding.status == "patch_rejected"
    assert [v.verdict for v in finding.verifications] == ["rejected"] * MAX_PATCH_ATTEMPTS
    first = finding.verifications[0]
    recheck = next(c for c in first.checks if c.name.value == "original_check_now_fails_to_reproduce")
    assert not recheck.passed
    assert "remediation.exhausted" in [e.action for e in res.audit]
    # Fortify's step runs alongside remediation, but an unresolved finding is never hardened.
    assert finding.status != "hardened" and not finding.recommendations


@pytest.mark.boundary
def test_patch_retry_receives_rejection_reasons_but_no_verify_transcript(intel, driver, library, tmp_path):
    orch, gateway = build(intel, driver, library, tmp_path, ineffective=True)
    orch.run()
    patch_calls = [c for c in gateway.provider.calls if c.agent is AgentName.PATCH]
    second_attempt = [c for c in patch_calls if "This is attempt 2" in str(c.messages[0]["content"])]
    assert second_attempt, "the retry prompt should state the attempt number"
    prompt = str(second_attempt[0].messages[0]["content"])
    assert "rejection_reasons" in prompt
    assert "original_check_now_fails_to_reproduce" in prompt
    # machine reasons only: Verify's own summary text must not be handed over
    assert "Applied the diff to a fresh checkout" not in prompt


@pytest.mark.boundary
def test_verify_rejects_edits_to_preexisting_tests_without_configured_protection(
    intel: LocalIntel, driver: LocalProcessDriver, library: CheckLibrary, tmp_path: Path
) -> None:
    from security_agents.agents import verify as verify_agent
    from security_agents.sandbox.workspace import fresh_checkout, unified_diff
    from security_agents.tools import AuditSink, PatchApplier, ToolContext

    orch, _ = build(intel, driver, library, tmp_path)
    assert orch.config.protected_tests == []
    protected_tests = orch._protected_tests()

    work = tmp_path / "preexisting-test"
    wt = fresh_checkout(intel.snapshot, work / "wt")
    protected = wt / "tests" / "test_api.py"
    protected.write_text(protected.read_text().replace("== 404", "in (200, 404)"))
    diff = unified_diff(intel.snapshot.root, wt, ["tests/test_api.py"])

    applier = PatchApplier(
        intel=intel,
        artifacts={
            "pat_existing_test": {
                "diff": diff,
                "plan_files": ["tests/test_api.py"],
                "protected_tests": protected_tests,
            }
        },
        workdir=work,
    )
    ctx = ToolContext(
        assessment_id="asm_existing_test",
        agent=AgentName.VERIFY,
        run_id="run_existing_test",
        step_key="verify",
        read_root=intel.snapshot.root,
        audit=AuditSink(),
    )
    facts = applier.apply_fresh(ctx, "pat_existing_test")

    assert facts["tampered_protected_tests"] == ["tests/test_api.py"]
    assert facts["out_of_scope_files"] == []
    verdict, checks, _ = verify_agent.compute_verdict(
        verify_agent.VerifyEvidence(
            apply_facts=dict(ctx.artifacts["verify_facts"]),
            recheck_runs=[],
            test_runs=[],
            baseline_failing=[],
            tests_added=[],
            protected_tests=protected_tests,
            original_check_ref="access_control.ownership@1",
            original_check_params={},
            candidate_id="pat_existing_test",
        )
    )
    assert verdict == "rejected"
    assert not next(c for c in checks if c.name.value == "no_test_tampering").passed


@pytest.mark.boundary
def test_verify_rejects_an_appended_duplicate_test_without_configured_protection(
    intel: LocalIntel, driver: LocalProcessDriver, library: CheckLibrary, tmp_path: Path
) -> None:
    from security_agents.agents import verify as verify_agent
    from security_agents.sandbox.workspace import fresh_checkout, unified_diff
    from security_agents.tools import AuditSink, PatchApplier, ToolContext

    orch, _ = build(intel, driver, library, tmp_path)
    assert orch.config.protected_tests == []
    protected_tests = orch._protected_tests()

    work = tmp_path / "appended-test"
    wt = fresh_checkout(intel.snapshot, work / "wt")
    protected = wt / "tests" / "test_api.py"
    protected.write_text(
        protected.read_text() + "\n\ndef test_customer_cannot_read_other_customer_profile():\n    pass\n"
    )
    diff = unified_diff(intel.snapshot.root, wt, ["tests/test_api.py"])

    applier = PatchApplier(
        intel=intel,
        artifacts={
            "pat_appended_test": {
                "diff": diff,
                "plan_files": ["tests/test_api.py"],
                "protected_tests": protected_tests,
            }
        },
        workdir=work,
    )
    ctx = ToolContext(
        assessment_id="asm_appended_test",
        agent=AgentName.VERIFY,
        run_id="run_appended_test",
        step_key="verify",
        read_root=intel.snapshot.root,
        audit=AuditSink(),
    )
    facts = applier.apply_fresh(ctx, "pat_appended_test")

    assert facts["tampered_protected_tests"] == ["tests/test_api.py"]
    verdict, checks, _ = verify_agent.compute_verdict(
        verify_agent.VerifyEvidence(
            apply_facts=dict(ctx.artifacts["verify_facts"]),
            recheck_runs=[],
            test_runs=[],
            baseline_failing=[],
            tests_added=[],
            protected_tests=protected_tests,
            original_check_ref="access_control.ownership@1",
            original_check_params={},
            candidate_id="pat_appended_test",
        )
    )
    assert verdict == "rejected"
    assert not next(c for c in checks if c.name.value == "no_test_tampering").passed


@pytest.mark.boundary
def test_verify_does_not_flag_a_new_test_under_recipe_test_roots(
    intel: LocalIntel, driver: LocalProcessDriver, library: CheckLibrary, tmp_path: Path
) -> None:
    from security_agents.sandbox.workspace import fresh_checkout, unified_diff
    from security_agents.tools import AuditSink, PatchApplier, ToolContext

    orch, _ = build(intel, driver, library, tmp_path)
    assert orch.config.protected_tests == []
    protected_tests = orch._protected_tests()

    work = tmp_path / "new-test"
    wt = fresh_checkout(intel.snapshot, work / "wt")
    new_test = wt / "tests" / "test_new_case.py"
    new_test.write_text("def test_new_case():\n    assert True\n")
    diff = unified_diff(intel.snapshot.root, wt, ["tests/test_new_case.py"])

    applier = PatchApplier(
        intel=intel,
        artifacts={
            "pat_new_test": {
                "diff": diff,
                "plan_files": ["tests/test_new_case.py"],
                "protected_tests": protected_tests,
            }
        },
        workdir=work,
    )
    ctx = ToolContext(
        assessment_id="asm_new_test",
        agent=AgentName.VERIFY,
        run_id="run_new_test",
        step_key="verify",
        read_root=intel.snapshot.root,
        audit=AuditSink(),
    )
    facts = applier.apply_fresh(ctx, "pat_new_test")

    assert facts["new_test_files"] == ["tests/test_new_case.py"]
    assert facts["tampered_protected_tests"] == []


@pytest.mark.boundary
def test_verify_accepts_a_new_recipe_declared_test(
    intel: LocalIntel, driver: LocalProcessDriver, library: CheckLibrary, tmp_path: Path
) -> None:
    variant = _variant_intel(
        intel,
        tmp_path,
        recipe_changes={"protected_tests": ["tests/test_new_regression.py"]},
    )
    orch, _ = build(variant, driver, library, tmp_path, test_path="tests/test_new_regression.py")
    result = orch.run()
    verification = result.findings[0].verifications[-1]

    assert verification.verdict == "accepted", verification.reasons
    no_tampering = next(check for check in verification.checks if check.name.value == "no_test_tampering")
    assert no_tampering.passed, no_tampering.detail


@pytest.mark.boundary
def test_verify_flags_a_modified_recipe_declared_test(
    intel: LocalIntel, driver: LocalProcessDriver, library: CheckLibrary, tmp_path: Path
) -> None:
    from security_agents.sandbox.workspace import fresh_checkout, unified_diff
    from security_agents.tools import AuditSink, PatchApplier, ToolContext

    variant = _variant_intel(
        intel,
        tmp_path,
        recipe_changes={"protected_tests": ["tests/test_api.py"]},
    )

    work = tmp_path / "recipe-declared-existing-test"
    wt = fresh_checkout(variant.snapshot, work / "wt")
    protected = wt / "tests" / "test_api.py"
    protected.write_text(protected.read_text().replace("== 404", "in (200, 404)"))
    diff = unified_diff(variant.snapshot.root, wt, ["tests/test_api.py"])
    applier = PatchApplier(
        intel=variant,
        artifacts={
            "pat_recipe_existing_test": {
                "diff": diff,
                "plan_files": ["tests/test_api.py"],
                "protected_tests": ["tests/test_api.py"],
            }
        },
        workdir=work,
    )
    ctx = ToolContext(
        assessment_id="asm_recipe_existing_test",
        agent=AgentName.VERIFY,
        run_id="run_recipe_existing_test",
        step_key="verify",
        read_root=variant.snapshot.root,
        audit=AuditSink(),
    )

    facts = applier.apply_fresh(ctx, "pat_recipe_existing_test")

    assert facts["tampered_protected_tests"] == ["tests/test_api.py"]


def _apply_fresh_diff(
    intel: LocalIntel,
    tmp_path: Path,
    diff: str,
    plan_files: list[str],
    protected_tests: list[str] | None = None,
) -> tuple[dict[str, Any], Any]:
    from security_agents.tools import AuditSink, PatchApplier, ToolContext

    patch_id = "pat_runner_config"
    applier = PatchApplier(
        intel=intel,
        artifacts={
            patch_id: {
                "diff": diff,
                "plan_files": plan_files,
                "protected_tests": protected_tests or [],
            }
        },
        workdir=tmp_path / "verify",
    )
    ctx = ToolContext(
        assessment_id="asm_runner_config",
        agent=AgentName.VERIFY,
        run_id="run_runner_config",
        step_key="verify",
        read_root=intel.snapshot.root,
        audit=AuditSink(),
    )
    return applier.apply_fresh(ctx, patch_id), ctx


_DESELECT_PROTECTED_TEST = (
    "def pytest_collection_modifyitems(items):\n"
    "    items[:] = [item for item in items if "
    "'tests/test_api.py::test_customer_cannot_read_other_customer_profile' "
    "not in item.nodeid]\n"
)


def test_runner_config_diff_paths_include_deleted_and_renamed_paths() -> None:
    from security_agents.sandbox.workspace import diff_paths

    rename_diff = """diff --git a/pytest.ini b/tests/pytest.ini
similarity index 100%
rename from pytest.ini
rename to tests/pytest.ini
"""
    deleted_diff = """diff --git a/setup.cfg b/setup.cfg
deleted file mode 100644
--- a/setup.cfg
+++ /dev/null
"""
    assert diff_paths(rename_diff) == ["pytest.ini", "tests/pytest.ini"]
    assert diff_paths(deleted_diff) == ["setup.cfg"]


def _new_nested_conftest_patch(intel: LocalIntel, tmp_path: Path) -> tuple[Path, str]:
    from security_agents.sandbox.workspace import fresh_checkout, unified_diff

    path = "tests/helpers/conftest.py"
    source = fresh_checkout(intel.snapshot, tmp_path / "patch-worktree")
    conftest = source / path
    conftest.parent.mkdir(parents=True, exist_ok=True)
    conftest.write_text(_DESELECT_PROTECTED_TEST, encoding="utf-8")
    return source, unified_diff(intel.snapshot.root, source, [path])


def _synthetic_test_target(tmp_path: Path, *, tests_package: bool) -> LocalIntel:
    target = tmp_path / "synthetic-target"
    package = target / "pkg"
    tests = target / "tests"
    package.mkdir(parents=True)
    tests.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    if tests_package:
        (tests / "__init__.py").write_text("", encoding="utf-8")
    (tests / "test_api.py").write_text(
        "from pkg.app import value\n\ndef test_value():\n    assert value() == 1\n",
        encoding="utf-8",
    )
    (target / "build_recipe.json").write_text(
        json.dumps({"test_roots": ["tests"], "test_command": ["-q", "tests"]}),
        encoding="utf-8",
    )
    snapshot = SnapshotHandle.from_directory(
        target,
        tmp_path / "synthetic-snapshot",
        snapshot_id="synthetic-test-root",
        repo_id="repo_synthetic",
    )
    return LocalIntel(snapshot, expectations=[])


def _symlink_test_target(tmp_path: Path, layout: str) -> LocalIntel:
    target = tmp_path / f"symlink-target-{layout}"
    (target / "pkg").mkdir(parents=True)
    (target / "spec").mkdir()
    (target / "tests").mkdir()
    (target / "pkg/__init__.py").write_text("", encoding="utf-8")
    (target / "pkg/app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (target / "spec/test_core.py").write_text(
        "from pkg.app import value\n\n\ndef test_core():\n    assert value() == 1\n",
        encoding="utf-8",
    )
    (target / "build_recipe.json").write_text(
        json.dumps({"test_roots": ["tests"], "test_command": ["-q", "tests"]}),
        encoding="utf-8",
    )
    snapshot = SnapshotHandle.from_directory(
        target,
        tmp_path / f"symlink-snapshot-{layout}",
        snapshot_id=f"symlink-{layout}",
        repo_id="repo_symlink",
    )
    shutil.rmtree(snapshot.root / "tests")
    if layout == "nested":
        (snapshot.root / "tests").mkdir()
        (snapshot.root / "tests/shared").symlink_to("../spec", target_is_directory=True)
    else:
        (snapshot.root / "tests").symlink_to("spec", target_is_directory=True)
    return LocalIntel(snapshot, expectations=[])


def _apply_synthetic_test_patch(
    intel: LocalIntel, tmp_path: Path, new_files: dict[str, str]
) -> tuple[dict[str, Any], Any]:
    from security_agents.sandbox.workspace import fresh_checkout, unified_diff
    from security_agents.tools import AuditSink, PatchApplier, ToolContext

    patch_root = fresh_checkout(intel.snapshot, tmp_path / "synthetic-patch")
    changed = ["pkg/app.py", *new_files]
    (patch_root / "pkg/app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
    for rel, content in new_files.items():
        path = patch_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    patch_id = "pat_synthetic_test_root"
    applier = PatchApplier(
        intel=intel,
        artifacts={
            patch_id: {
                "diff": unified_diff(intel.snapshot.root, patch_root, changed),
                "plan_files": ["pkg/app.py"],
                "protected_tests": ["tests/test_api.py"],
                "tests_added": ["tests/test_aaa.py"],
            }
        },
        workdir=tmp_path / "synthetic-verify-work",
    )
    ctx = ToolContext(
        assessment_id="asm_synthetic_test_root",
        agent=AgentName.VERIFY,
        run_id="run_synthetic_test_root",
        step_key="verify",
        read_root=intel.snapshot.root,
        audit=AuditSink(),
    )
    return applier.apply_fresh(ctx, patch_id), ctx


def _test_files_under(root: Path, test_root: str = "tests") -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    start = root / test_root
    for current, _, names in os.walk(start, followlinks=False):
        for name in names:
            path = Path(current) / name
            if path.is_file() and not path.is_symlink():
                files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def _synthetic_test_runner(
    intel: LocalIntel,
    driver: LocalProcessDriver,
    library: CheckLibrary,
    tmp_path: Path,
    *,
    isolated_suite: bool,
) -> Any:
    orch, _ = build(intel, driver, library, tmp_path, scripts={"unused": []})

    def verify_workspace(ctx: Any) -> Path:
        return ctx.artifacts.get("verify_workspace") or intel.snapshot.root

    def verify_suite_workspace(ctx: Any) -> Path:
        return ctx.artifacts.get("verify_suite_workspace")

    return orch._test_runner(
        verify_workspace,
        suite_workspace_provider=verify_suite_workspace if isolated_suite else None,
    )


@pytest.mark.boundary
def test_verify_project_suite_ignores_patch_added_test_module(
    driver: LocalProcessDriver, library: CheckLibrary, tmp_path: Path
) -> None:
    intel = _synthetic_test_target(tmp_path, tests_package=True)
    facts, ctx = _apply_synthetic_test_patch(
        intel,
        tmp_path,
        {
            "tests/test_aaa.py": (
                "import tests.test_api as protected\n"
                "protected.test_value = lambda: None\n\n"
                "def test_added_module_runs():\n"
                "    assert True\n"
            )
        },
    )
    assert facts["applied"], facts["apply_error"]
    assert facts["out_of_scope_files"] == []

    legacy = _synthetic_test_runner(intel, driver, library, tmp_path, isolated_suite=False)
    legacy_result = legacy.run(ctx, "project_suite", [])
    assert legacy_result["failing_tests"] == []

    runner = _synthetic_test_runner(intel, driver, library, tmp_path, isolated_suite=True)
    suite_result = runner.run(ctx, "project_suite", [])
    assert "tests/test_api.py::test_value" in suite_result["failing_tests"]

    suite_root = ctx.artifacts["verify_suite_workspace"]
    verify_root = ctx.artifacts["verify_workspace"]
    assert not (suite_root / "tests/test_aaa.py").exists()
    assert _test_files_under(suite_root) == _test_files_under(intel.snapshot.root)
    assert (suite_root / "pkg/app.py").read_bytes() == (verify_root / "pkg/app.py").read_bytes()

    ctx.artifacts["tests_added"] = ["tests/test_aaa.py"]
    added_result = runner.run(ctx, "added_tests", [])
    assert added_result["passed"] == 1, added_result["stdout_tail"]


@pytest.mark.boundary
def test_verify_project_suite_rejects_node_ids_without_running(
    driver: LocalProcessDriver,
    library: CheckLibrary,
    tmp_path: Path,
) -> None:
    intel = _synthetic_test_target(tmp_path, tests_package=True)
    _, ctx = _apply_synthetic_test_patch(
        intel,
        tmp_path,
        {
            "tests/test_aaa.py": (
                "import tests.test_api as protected\n"
                "protected.test_value = lambda: None\n\n"
                "def test_added_module_runs():\n"
                "    assert True\n"
            )
        },
    )
    runner = _synthetic_test_runner(intel, driver, library, tmp_path, isolated_suite=True)
    spy = Mock(wraps=driver)
    runner.driver = spy
    result = runner.run(
        ctx,
        "project_suite",
        ["tests/test_aaa.py::test_added_module_runs", "tests/test_api.py::test_value"],
    )

    assert result == {
        "error": "PROJECT_SUITE_NODE_IDS",
        "detail": "Verify's project_suite runs the full pinned suite; node_ids are not allowed",
    }
    assert spy.run.call_count == 0

    suite_result = runner.run(ctx, "project_suite", [])
    assert "tests/test_api.py::test_value" in suite_result["failing_tests"]
    assert spy.run.call_count == 1


@pytest.mark.boundary
def test_verify_rejects_suite_evidence_collected_before_patch_apply(
    driver: LocalProcessDriver, library: CheckLibrary, tmp_path: Path
) -> None:
    from security_agents.agents import verify as verify_agent
    from security_agents.sandbox.workspace import fresh_checkout, unified_diff
    from security_agents.tools import AuditSink, PatchApplier, ToolContext

    intel = _synthetic_test_target(tmp_path, tests_package=True)
    patch_root = fresh_checkout(intel.snapshot, tmp_path / "b2-patch")
    (patch_root / "pkg/app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
    added = patch_root / "tests/test_aaa.py"
    added.write_text(
        "from pkg.app import value\n\n\ndef test_regression():\n    assert value() == 2\n",
        encoding="utf-8",
    )
    patch_id = "pat_pre_apply_suite"
    applier = PatchApplier(
        intel=intel,
        artifacts={
            patch_id: {
                "diff": unified_diff(intel.snapshot.root, patch_root, ["pkg/app.py", "tests/test_aaa.py"]),
                "plan_files": ["pkg/app.py"],
                "protected_tests": ["tests/test_api.py"],
                "tests_added": ["tests/test_aaa.py"],
            }
        },
        workdir=tmp_path / "b2-verify",
    )
    ctx = ToolContext(
        assessment_id="asm_pre_apply_suite",
        agent=AgentName.VERIFY,
        run_id="run_pre_apply_suite",
        step_key="verify",
        read_root=intel.snapshot.root,
        audit=AuditSink(),
    )
    runner = _synthetic_test_runner(intel, driver, library, tmp_path, isolated_suite=True)

    pre_apply_suite = runner.run(ctx, "project_suite", [])
    assert pre_apply_suite == {
        "error": "NO_VERIFY_WORKSPACE",
        "detail": "patch.apply_fresh must succeed before project_suite",
    }

    facts = applier.apply_fresh(ctx, patch_id)
    assert facts["applied"], facts["apply_error"]
    ctx.artifacts["tests_added"] = ["tests/test_aaa.py"]
    added_run = runner.run(ctx, "added_tests", [])
    added_run["workspace_role"] = "patched"
    evidence = verify_agent.VerifyEvidence(
        apply_facts=dict(ctx.artifacts["verify_facts"]),
        recheck_runs=[{"template_ref": "synthetic@1", "matches_expectation": True, "parameters": {}}],
        test_runs=[pre_apply_suite, added_run],
        baseline_failing=[],
        tests_added=["tests/test_aaa.py"],
        protected_tests=["tests/test_api.py"],
        original_check_ref="synthetic@1",
        original_check_params={},
        candidate_id=patch_id,
    )

    verdict, checks, _ = verify_agent.compute_verdict(evidence)
    assert verdict == "rejected"
    assert not next(c for c in checks if c.name.value == "functional_suite_passes").passed


@pytest.mark.boundary
def test_verify_project_suite_ignores_patch_loaded_pytest_plugin(
    driver: LocalProcessDriver, library: CheckLibrary, tmp_path: Path
) -> None:
    intel = _synthetic_test_target(tmp_path, tests_package=False)
    facts, ctx = _apply_synthetic_test_patch(
        intel,
        tmp_path,
        {
            "tests/test_aaa.py": (
                'pytest_plugins = ["tests.plug"]\n\ndef test_added_module_runs():\n    assert True\n'
            ),
            "tests/plug.py": (
                "def pytest_collection_modifyitems(items):\n"
                "    for item in items:\n"
                "        if item.nodeid.endswith('test_api.py::test_value'):\n"
                "            item.obj = lambda: None\n"
            ),
        },
    )
    assert facts["applied"], facts["apply_error"]
    assert facts["out_of_scope_files"] == []

    legacy = _synthetic_test_runner(intel, driver, library, tmp_path, isolated_suite=False)
    legacy_result = legacy.run(ctx, "project_suite", [])
    assert legacy_result["failing_tests"] == []

    runner = _synthetic_test_runner(intel, driver, library, tmp_path, isolated_suite=True)
    suite_result = runner.run(ctx, "project_suite", [])
    assert "tests/test_api.py::test_value" in suite_result["failing_tests"]

    suite_root = ctx.artifacts["verify_suite_workspace"]
    verify_root = ctx.artifacts["verify_workspace"]
    assert not (suite_root / "tests/test_aaa.py").exists()
    assert not (suite_root / "tests/plug.py").exists()
    assert _test_files_under(suite_root) == _test_files_under(intel.snapshot.root)
    assert (suite_root / "pkg/app.py").read_bytes() == (verify_root / "pkg/app.py").read_bytes()


@pytest.mark.boundary
@pytest.mark.parametrize(
    ("layout", "edit"),
    [
        ("nested", "logical"),
        ("nested", "target"),
        ("nested", "app"),
        ("root", "logical"),
        ("root", "target"),
        ("root", "app"),
    ],
    ids=[
        "nested-logical",
        "nested-target",
        "nested-app",
        "root-logical",
        "root-target",
        "root-app",
    ],
)
def test_protected_tests_follow_safe_directory_symlinks(
    layout: str,
    edit: str,
    driver: LocalProcessDriver,
    library: CheckLibrary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import security_agents.sandbox.workspace as workspace
    from security_agents.tools import AuditSink, PatchApplier, ToolContext

    intel = _symlink_test_target(tmp_path, layout)
    orch, _ = build(intel, driver, library, tmp_path, scripts={"unused": []})
    protected = orch._protected_tests()
    logical = "tests/shared/test_core.py" if layout == "nested" else "tests/test_core.py"
    assert logical in protected
    assert "spec/test_core.py" in protected

    if edit == "logical":
        changed = logical
    elif edit == "target":
        changed = "spec/test_core.py"
    else:
        changed = "pkg/app.py"

    diff = f"diff --git a/{changed} b/{changed}\n--- a/{changed}\n+++ b/{changed}\n"

    def apply_edit(root: Path, _diff: str) -> tuple[bool, str]:
        path = root / changed
        original_text = path.read_text(encoding="utf-8")
        if changed.endswith("test_core.py"):
            updated_text = original_text.replace("== 1", "== 2")
        else:
            updated_text = original_text.replace("return 1", "return 2")
        path.write_text(updated_text, encoding="utf-8")
        return True, ""

    monkeypatch.setattr(workspace, "apply_diff", apply_edit)
    patch_id = f"pat_symlink_{layout}_{edit}"
    applier = PatchApplier(
        intel=intel,
        artifacts={
            patch_id: {
                "diff": diff,
                "plan_files": [changed],
                "protected_tests": protected,
            }
        },
        workdir=tmp_path / f"symlink-verify-{layout}-{edit}",
    )
    ctx = ToolContext(
        assessment_id=f"asm_symlink_{layout}_{edit}",
        agent=AgentName.VERIFY,
        run_id=f"run_symlink_{layout}_{edit}",
        step_key="verify",
        read_root=intel.snapshot.root,
        audit=AuditSink(),
    )

    facts = applier.apply_fresh(ctx, patch_id)

    assert facts["applied"], facts["apply_error"]
    assert facts["out_of_scope_files"] == []
    if edit == "app":
        assert facts["tampered_protected_tests"] == []
    else:
        assert changed in facts["tampered_protected_tests"]


@pytest.mark.boundary
def test_test_root_discovery_preserves_aliases_and_protects_changed_alias(
    tmp_path: Path,
) -> None:
    from security_agents.sandbox.workspace import test_root_files
    from security_agents.tools import PatchApplier

    root = tmp_path / "repo"
    (root / "tests/z").mkdir(parents=True)
    (root / "spec").mkdir()
    (root / "spec/test_core.py").write_text("assert True\n", encoding="utf-8")
    (root / "tests/a").symlink_to("z", target_is_directory=True)
    (root / "tests/z/cycle").symlink_to("..", target_is_directory=True)
    (root / "tests/z/test_core.py").symlink_to("../../spec/test_core.py")

    protected = list(test_root_files(root, ("tests/",)))

    assert "tests/a/test_core.py" in protected
    assert "tests/z/test_core.py" in protected
    assert "spec/test_core.py" in protected
    diff = (
        "diff --git a/tests/z/test_core.py b/tests/z/test_core.py\n"
        "--- a/tests/z/test_core.py\n"
        "+++ b/tests/z/test_core.py\n"
        "@@ -1 +1 @@\n-assert True\n+assert False\n"
    )
    assert "tests/z/test_core.py" in PatchApplier._tampered_tests(diff, protected)


@pytest.mark.boundary
def test_test_root_discovery_budget_exhaustion_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import security_agents.sandbox.workspace as workspace
    from security_agents.contracts import ErrorCode, PlatformError

    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "tests/test_a.py").write_text("assert True\n", encoding="utf-8")
    monkeypatch.setattr(workspace, "MAX_TEST_ROOT_ENTRIES", 1)

    with pytest.raises(PlatformError) as exc:
        workspace.test_root_files(root, ("tests/",))

    assert exc.value.code == ErrorCode.SNAPSHOT_NOT_READY


@pytest.mark.boundary
def test_protected_test_discovery_errors_fail_closed_in_apply_fresh(
    intel: LocalIntel,
    driver: LocalProcessDriver,
    library: CheckLibrary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from security_agents.contracts import ErrorCode, PlatformError
    from security_agents.sandbox.workspace import test_root_files

    tests_dir = intel.snapshot.root / "tests"
    original_iterdir = Path.iterdir

    def fail_test_root(path: Path) -> Any:
        if path == tests_dir:
            raise OSError("simulated protected-test discovery failure")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", fail_test_root)
    with pytest.raises(PlatformError) as discovery_error:
        test_root_files(intel.snapshot.root, ("tests/",))
    assert discovery_error.value.code == ErrorCode.SNAPSHOT_NOT_READY
    orch, _ = build(intel, driver, library, tmp_path, scripts={"unused": []})
    protected = orch._protected_tests()
    assert any("protected-test discovery failed: SNAPSHOT_NOT_READY" in path for path in protected)

    diff = (
        "diff --git a/verify_probe.py b/verify_probe.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n+++ b/verify_probe.py\n"
        "@@ -0,0 +1 @@\n+value = 1\n"
    )
    facts, _ = _apply_fresh_diff(intel, tmp_path, diff, ["verify_probe.py"], protected)

    assert any(
        "protected-test discovery failed: SNAPSHOT_NOT_READY" in item
        for item in facts["tampered_protected_tests"]
    )


@pytest.mark.boundary
def test_apply_fresh_rejects_protected_dangling_symlink(
    intel: LocalIntel, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import security_agents.sandbox.workspace as workspace

    diff = """\
diff --git a/tests/test_api.py b/tests/test_api.py
old mode 100644
new mode 120000
--- a/tests/test_api.py
+++ b/tests/test_api.py
@@ -1,4 +1 @@
-from pkg.app import value
-
-def test_value():
-    assert value() == 1
+missing-target
"""

    def apply_dangling(root: Path, _diff: str) -> tuple[bool, str]:
        target = root / "tests/test_api.py"
        target.unlink()
        target.symlink_to("missing-target")
        return True, ""

    monkeypatch.setattr(workspace, "apply_diff", apply_dangling)
    facts, ctx = _apply_fresh_diff(
        intel,
        tmp_path,
        diff,
        ["tests/test_api.py"],
        ["tests/test_api.py"],
    )

    assert facts["applied"] is False
    assert facts["apply_error"].startswith("verify suite workspace:")
    assert ctx.artifacts.get("verify_suite_workspace") is None
    assert "tests/test_api.py" in facts["tampered_protected_tests"]


@pytest.mark.boundary
def test_new_nested_conftest_is_flagged_by_apply_fresh(intel: LocalIntel, tmp_path: Path) -> None:
    path = "tests/helpers/conftest.py"
    _, diff = _new_nested_conftest_patch(intel, tmp_path)
    facts, _ = _apply_fresh_diff(
        intel,
        tmp_path,
        diff,
        plan_files=[],
        protected_tests=["tests/test_api.py"],
    )

    assert facts["applied"], facts["apply_error"]
    assert facts["out_of_scope_files"] == []
    assert path in facts["tampered_protected_tests"]


@pytest.mark.boundary
def test_new_nested_conftest_deselects_a_protected_test_in_verify_workspace(
    intel: LocalIntel, tmp_path: Path
) -> None:
    _, diff = _new_nested_conftest_patch(intel, tmp_path)
    facts, ctx = _apply_fresh_diff(
        intel,
        tmp_path,
        diff,
        plan_files=[],
        protected_tests=["tests/test_api.py"],
    )
    assert facts["applied"], facts["apply_error"]
    assert facts["out_of_scope_files"] == []

    def collect(root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    node_id = "test_api.py::test_customer_cannot_read_other_customer_profile"
    original = collect(intel.snapshot.root)
    patched = collect(ctx.artifacts["verify_workspace"])
    assert original.returncode == 0, original.stdout + original.stderr
    assert patched.returncode == 0, patched.stdout + patched.stderr
    assert node_id in original.stdout
    assert node_id not in patched.stdout


@pytest.mark.boundary
def test_orchestrator_rejects_a_new_nested_conftest_that_deselects_a_protected_test(
    intel: LocalIntel,
    driver: LocalProcessDriver,
    library: CheckLibrary,
    tmp_path: Path,
) -> None:
    path = "tests/helpers/conftest.py"
    orch, _ = build(intel, driver, library, tmp_path, extra_patch_files={path: _DESELECT_PROTECTED_TEST})

    result = orch.run()
    candidate = result.findings[0].candidates[-1]
    verification = result.findings[0].verifications[-1]
    no_tampering = next(check for check in verification.checks if check.name.value == "no_test_tampering")

    assert path in candidate.files_changed
    assert verification.verdict == "rejected", verification.reasons
    assert not no_tampering.passed, no_tampering.detail
    assert path in no_tampering.detail


@pytest.mark.boundary
@pytest.mark.parametrize(
    ("scenario", "path", "content", "expected_tampered"),
    [
        ("modify-existing-conftest", "tests/conftest.py", "# changed\n", True),
        ("delete-existing-conftest", "tests/conftest.py", None, True),
        ("new-root-conftest", "conftest.py", "pytest_plugins = []\n", True),
        ("new-pytest-ini", "pytest.ini", "[pytest]\naddopts = -q\n", True),
        ("new-nested-pytest-ini", "tests/pytest.ini", "[pytest]\naddopts = -q\n", True),
        ("new-hidden-pytest-ini", "tests/.pytest.ini", "[pytest]\naddopts = -q\n", True),
        ("new-pytest-toml", "pytest.toml", '[pytest]\naddopts = ["-q"]\n', True),
        ("new-hidden-pytest-toml", ".pytest.toml", '[pytest]\naddopts = ["-q"]\n', True),
        ("shadow-pytest-module", "pytest.py", "# shadow\n", True),
        ("shadow-pytest-package", "pytest/__init__.py", "# shadow\n", True),
        ("shadow-pytest-internal-package", "_pytest/__init__.py", "# shadow\n", True),
        ("shadow-pluggy-module", "pluggy.py", "# shadow\n", True),
        ("shadow-pluggy-package", "pluggy/__init__.py", "# shadow\n", True),
        ("shadow-py-module", "py.py", "# shadow\n", True),
        ("shadow-py-package", "py/__init__.py", "# shadow\n", True),
        ("shadow-sitecustomize", "sitecustomize.py", "# shadow\n", True),
        ("shadow-usercustomize", "usercustomize.py", "# shadow\n", True),
        ("root-pth-file", "runner.pth", "import pytest\n", True),
        ("tox-pytest-section", "tox.ini", "[pytest]\naddopts = -q\n", True),
        ("setup-pytest-section", "setup.cfg", "[tool:pytest]\naddopts = -q\n", True),
        (
            "setup-pytest11-entry-point",
            "setup.cfg",
            "[options.entry_points]\npytest11 =\n    example = example.plugin\n",
            True,
        ),
        ("pyproject-pytest-table", "pyproject.toml", "pytest-table", True),
        ("pyproject-pytest11-entry-point", "pyproject.toml", "pytest11-entry-point", True),
        ("pyproject-poetry-pytest11-plugin", "pyproject.toml", "poetry-pytest11-plugin", True),
        ("unparsable-pyproject", "pyproject.toml", "not = [toml\n", True),
        ("pyproject-dependency-only", "pyproject.toml", "dependency-only", False),
        ("setup-install-requires-only", "setup.cfg", "[options]\ninstall_requires =\n    example\n", False),
        ("tox-testenv-only", "tox.ini", "[testenv]\ncommands = pytest\n", False),
    ],
)
def test_apply_fresh_flags_effective_runner_configuration_changes(
    scenario: str,
    path: str,
    content: str | None,
    expected_tampered: bool,
    intel: LocalIntel,
    tmp_path: Path,
) -> None:
    from security_agents.sandbox.workspace import fresh_checkout, unified_diff

    source = fresh_checkout(intel.snapshot, tmp_path / "patch-worktree")
    config = source / path
    if content is None:
        config.unlink()
    else:
        config.parent.mkdir(parents=True, exist_ok=True)
        if scenario == "modify-existing-conftest":
            config.write_text(config.read_text(encoding="utf-8") + content, encoding="utf-8")
        elif scenario == "pyproject-pytest-table":
            current = config.read_text(encoding="utf-8")
            config.write_text(
                current.replace(
                    'testpaths = ["tests"]',
                    'testpaths = ["tests"]\naddopts = "--deselect=tests/test_api.py::'
                    'test_customer_cannot_read_other_customer_profile"',
                ),
                encoding="utf-8",
            )
        elif scenario == "pyproject-pytest11-entry-point":
            config.write_text(
                config.read_text(encoding="utf-8")
                + '\n[project.entry-points.pytest11]\nexample = "example.plugin"\n',
                encoding="utf-8",
            )
        elif scenario == "pyproject-poetry-pytest11-plugin":
            config.write_text(
                config.read_text(encoding="utf-8")
                + '\n[tool.poetry.plugins.pytest11]\nexample = "example.plugin"\n',
                encoding="utf-8",
            )
        elif scenario == "pyproject-dependency-only":
            config.write_text(
                config.read_text(encoding="utf-8").replace("fastapi>=0.110", "fastapi>=0.111"),
                encoding="utf-8",
            )
        else:
            config.write_text(content, encoding="utf-8")

    diff = unified_diff(intel.snapshot.root, source, [path])
    facts, _ = _apply_fresh_diff(intel, tmp_path, diff, plan_files=[path])

    assert facts["applied"], facts["apply_error"]
    assert (path in facts["tampered_protected_tests"]) is expected_tampered, scenario


def test_sandbox_entry_imports_pytest_and_pluggy_before_workspace_path() -> None:
    entry_path = Path(__file__).parents[1] / "security_agents" / "sandbox" / "entry.py"
    main = next(
        node
        for node in ast.walk(ast.parse(entry_path.read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    workspace_path_assignment = next(
        node
        for node in ast.walk(main)
        if isinstance(node, ast.Assign)
        and any(ast.unparse(target) == "sys.path[:0]" for target in node.targets)
    )
    imports = {
        alias.name: node.lineno
        for node in ast.walk(main)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert imports.get("pytest", 0) < workspace_path_assignment.lineno
    assert imports.get("pluggy", 0) < workspace_path_assignment.lineno


@pytest.mark.boundary
@pytest.mark.parametrize(
    ("config_path", "config_text", "changed_path"),
    [
        ("conftest.py", "pytest_plugins = ['pkg.plug']\n", "pkg/plug.py"),
        ("pytest.ini", "[pytest]\naddopts = -p pkg.plug\n", "pkg/plug.py"),
        ("tox.ini", "[pytest]\naddopts = -ppkg.plug\n", "pkg/plug/helper.py"),
        ("setup.cfg", "[tool:pytest]\naddopts = -p pkg.plug\n", "pkg/plug.py"),
        ("pyproject.toml", "[tool.pytest.ini_options]\naddopts = '-ppkg.plug'\n", "pkg/plug.py"),
        (
            "setup.cfg",
            "[options.entry_points]\npytest11 =\n    example = pkg.plug\n",
            "pkg/plug.py",
        ),
        (
            "pyproject.toml",
            "[project.entry-points.pytest11]\nexample = 'pkg.plug:Plugin'\n",
            "pkg/plug.py",
        ),
        (
            "pyproject.toml",
            "[tool.poetry.plugins.pytest11]\nexample = 'pkg.plug:Plugin'\n",
            "pkg/plug.py",
        ),
    ],
    ids=[
        "literal-conftest-plugin",
        "pytest-ini-addopts",
        "tox-addopts-package-plugin",
        "setup-cfg-addopts",
        "pyproject-addopts",
        "setup-cfg-pytest11",
        "pyproject-pytest11",
        "poetry-pytest11",
    ],
)
def test_pinned_plugin_module_edits_are_flagged_but_unrelated_modules_are_not(
    config_path: str,
    config_text: str,
    changed_path: str,
    tmp_path: Path,
) -> None:
    from security_agents.sandbox.workspace import unified_diff
    from security_agents.tools import PatchApplier

    snapshot_root = tmp_path / "snapshot"
    patched_root = tmp_path / "patched"
    snapshot_root.mkdir()
    config = snapshot_root / config_path
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(config_text, encoding="utf-8")
    plugin_file = snapshot_root / changed_path
    plugin_file.parent.mkdir(parents=True, exist_ok=True)
    if changed_path.endswith("/helper.py"):
        (snapshot_root / "pkg/plug/__init__.py").write_text("", encoding="utf-8")
    plugin_file.write_text(
        "def pytest_collection_modifyitems(items):\n"
        "    items[:] = [item for item in items if 'test_value' not in item.nodeid]\n",
        encoding="utf-8",
    )
    unrelated_file = snapshot_root / "pkg/unrelated.py"
    unrelated_file.write_text("VALUE = 1\n", encoding="utf-8")
    shutil.copytree(snapshot_root, patched_root)
    changed_plugin = patched_root / changed_path
    changed_plugin.write_text(
        changed_plugin.read_text(encoding="utf-8") + "\n# changed\n",
        encoding="utf-8",
    )

    plugin_diff = unified_diff(snapshot_root, patched_root, [changed_path])
    plugin_tampering = PatchApplier._tampered_runner_config(plugin_diff, snapshot_root, patched_root)

    assert changed_path in plugin_tampering

    unrelated_root = tmp_path / "unrelated"
    shutil.copytree(snapshot_root, unrelated_root)
    unrelated = unrelated_root / "pkg/unrelated.py"
    unrelated.write_text("VALUE = 2\n", encoding="utf-8")
    unrelated_diff = unified_diff(snapshot_root, unrelated_root, ["pkg/unrelated.py"])

    assert PatchApplier._tampered_runner_config(unrelated_diff, snapshot_root, unrelated_root) == []


@pytest.mark.boundary
def test_dynamic_pinned_plugin_declarations_are_recorded_without_broad_python_flags(
    tmp_path: Path,
) -> None:
    from security_agents.sandbox.workspace import unified_diff
    from security_agents.tools import PatchApplier

    snapshot_root = tmp_path / "dynamic-plugin-snapshot"
    patched_root = tmp_path / "dynamic-plugin-patched"
    snapshot_root.mkdir()
    (snapshot_root / "conftest.py").write_text(
        "pytest_plugins = discover_plugins()\n",
        encoding="utf-8",
    )
    (snapshot_root / "pkg").mkdir()
    (snapshot_root / "pkg/unrelated.py").write_text("VALUE = 1\n", encoding="utf-8")
    shutil.copytree(snapshot_root, patched_root)
    (patched_root / "pkg/unrelated.py").write_text("VALUE = 2\n", encoding="utf-8")
    diff = unified_diff(snapshot_root, patched_root, ["pkg/unrelated.py"])
    residuals: list[str] = []

    assert (
        PatchApplier._tampered_runner_config(
            diff,
            snapshot_root,
            patched_root,
            residuals=residuals,
        )
        == []
    )
    assert residuals == ["conftest.py"]


@pytest.mark.boundary
def test_apply_fresh_rejects_diff_headers_with_unsupported_prefix(
    intel: LocalIntel,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from security_agents.sandbox import workspace

    called = False

    def apply_unsupported_diff(root: Path, _diff: str) -> tuple[bool, str]:
        nonlocal called
        called = True
        (root / "conftest.py").write_text("pytest_plugins = []\n", encoding="utf-8")
        return True, ""

    monkeypatch.setattr(workspace, "apply_diff", apply_unsupported_diff)
    diff = (
        "diff --git x/conftest.py x/conftest.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ x/conftest.py\n"
        "@@ -0,0 +1 @@\n"
        "+pytest_plugins = []\n"
    )

    facts, _ = _apply_fresh_diff(intel, tmp_path, diff, plan_files=["conftest.py"])

    assert not facts["applied"]
    assert facts["apply_error"] == "unsupported diff path prefix"
    assert not called


def _runner_config_tampering_for_test(
    tmp_path: Path,
    *,
    config_files: dict[str, str],
    changed_path: str,
    patched_text: str,
    test_command: list[str] | None = None,
    pinned_text: str = "VALUE = 1\n",
) -> list[str]:
    from security_agents.sandbox.workspace import unified_diff
    from security_agents.tools import PatchApplier

    snapshot_root = tmp_path / "snapshot"
    snapshot_root.mkdir()
    (snapshot_root / "build_recipe.json").write_text(
        json.dumps(
            {
                "test_roots": ["tests"],
                "test_command": test_command or ["-q", "tests"],
            }
        ),
        encoding="utf-8",
    )
    for path, content in config_files.items():
        config = snapshot_root / path
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(content, encoding="utf-8")
    plugin_file = snapshot_root / changed_path
    plugin_file.parent.mkdir(parents=True, exist_ok=True)
    plugin_file.write_text(pinned_text, encoding="utf-8")

    patched_root = tmp_path / "patched"
    shutil.copytree(snapshot_root, patched_root)
    (patched_root / changed_path).write_text(patched_text, encoding="utf-8")
    diff = unified_diff(snapshot_root, patched_root, [changed_path])
    return PatchApplier._tampered_runner_config(diff, snapshot_root, patched_root)


@pytest.mark.boundary
@pytest.mark.parametrize(
    ("config_files", "test_command", "changed_path", "patched_text"),
    [
        pytest.param(
            {
                "pytest.ini": "[pytest]\npythonpath = src\n",
                "conftest.py": 'pytest_plugins = ["mypkg.plug"]\n',
            },
            ["-q", "tests"],
            "src/mypkg/plug.py",
            "VALUE = 2\n\ndef pytest_collection_modifyitems(items):\n    items.clear()\n",
            id="pythonpath-src-and-conftest-plugin",
        ),
        pytest.param(
            {},
            ["-q", "-p", "pkg.plug", "tests"],
            "pkg/plug.py",
            "VALUE = 2\n",
            id="recipe-test-command-plugin",
        ),
        pytest.param(
            {"tests/pytest.ini": "[pytest]\naddopts = -p pkg.plug\n"},
            ["-q", "tests"],
            "pkg/plug.py",
            "VALUE = 2\n",
            id="nested-pytest-ini-plugin",
        ),
        pytest.param(
            {"tests/test_loader.py": 'pytest_plugins = ["pkg.plug"]\n'},
            ["-q", "tests"],
            "pkg/plug.py",
            "VALUE = 2\n",
            id="test-module-plugin-declaration",
        ),
    ],
)
def test_pinned_plugin_discovery_covers_additional_sources(
    config_files: dict[str, str],
    test_command: list[str],
    changed_path: str,
    patched_text: str,
    tmp_path: Path,
) -> None:
    tampered = _runner_config_tampering_for_test(
        tmp_path,
        config_files=config_files,
        changed_path=changed_path,
        patched_text=patched_text,
        test_command=test_command,
    )

    assert changed_path in tampered


@pytest.mark.boundary
@pytest.mark.parametrize(
    "test_command",
    [
        ["-c", "config/testing.ini", "tests"],
        ["-cconfig/testing.ini", "tests"],
        ["--config-file", "config/testing.ini", "tests"],
        ["--config-file=config/testing.ini", "tests"],
    ],
    ids=["short-separated", "short-attached", "long-separated", "long-equals"],
)
def test_pinned_custom_pytest_config_is_byte_protected(test_command: list[str], tmp_path: Path) -> None:
    path = "config/testing.ini"
    tampered = _runner_config_tampering_for_test(
        tmp_path,
        config_files={},
        changed_path=path,
        pinned_text="[pytest]\n",
        patched_text="[pytest]\naddopts = --deselect=tests/test_api.py::test_value\n",
        test_command=test_command,
    )

    assert path in tampered


@pytest.mark.boundary
@pytest.mark.parametrize(
    "test_command",
    [
        ["--rootdir", "config-root", "tests"],
        ["--rootdir=config-root", "tests"],
    ],
    ids=["rootdir-separated", "rootdir-equals"],
)
def test_pinned_rootdir_config_is_byte_protected(test_command: list[str], tmp_path: Path) -> None:
    path = "config-root/pytest.ini"
    tampered = _runner_config_tampering_for_test(
        tmp_path,
        config_files={},
        changed_path=path,
        pinned_text="[pytest]\n",
        patched_text="[pytest]\naddopts = --deselect=tests/test_api.py::test_value\n",
        test_command=test_command,
    )

    assert path in tampered


@pytest.mark.boundary
@pytest.mark.parametrize(
    ("path", "pinned_text", "patched_text"),
    [
        (
            "tox.ini",
            "[pytest]\npython_files = check_*.py\n",
            "[DEFAULT]\npython_files = check_*.py\n[pytest]\n",
        ),
        (
            "setup.cfg",
            "[tool:pytest]\npython_files = check_*.py\n",
            "[DEFAULT]\npython_files = check_*.py\n[tool:pytest]\n",
        ),
    ],
    ids=["tox-default-move", "setup-cfg-default-move"],
)
def test_pytest_ini_defaults_cannot_hide_collection_options(
    path: str,
    pinned_text: str,
    patched_text: str,
    tmp_path: Path,
) -> None:
    tampered = _runner_config_tampering_for_test(
        tmp_path,
        config_files={},
        changed_path=path,
        pinned_text=pinned_text,
        patched_text=patched_text,
    )

    assert path in tampered


@pytest.mark.boundary
def test_unrelated_tox_testenv_edit_is_not_runner_tampering(tmp_path: Path) -> None:
    path = "tox.ini"
    tampered = _runner_config_tampering_for_test(
        tmp_path,
        config_files={},
        changed_path=path,
        pinned_text="[pytest]\npython_files = check_*.py\n[testenv]\ncommands = pytest\n",
        patched_text="[pytest]\npython_files = check_*.py\n[testenv]\ncommands = pytest -q\n",
    )

    assert tampered == []


@pytest.mark.boundary
@pytest.mark.parametrize(
    ("construct",),
    [
        ("def pytest_collection_modifyitems(items):\n    items.clear()\n",),
        ("async def pytest_report_header(config):\n    return 'patched'\n",),
        ("@pytest.hookimpl\ndef setup_plugin():\n    return None\n",),
        ("@hookimpl\ndef setup_plugin():\n    return None\n",),
        ("import _pytest\n",),
        ("from _pytest import hookspec\n",),
        ("import pluggy\n",),
        ("from pluggy import HookimplMarker\n",),
        ('pytest_plugins = ["pkg.plug"]\n',),
    ],
)
def test_new_pytest_hook_constructs_in_app_modules_are_flagged(
    construct: str,
    tmp_path: Path,
) -> None:
    path = "pkg/app.py"
    tampered = _runner_config_tampering_for_test(
        tmp_path,
        config_files={},
        changed_path=path,
        patched_text=f"VALUE = 1\n\n{construct}",
    )

    assert path in tampered


@pytest.mark.boundary
@pytest.mark.parametrize(
    ("pinned_text", "patched_text"),
    [
        ("VALUE = 1\n", "VALUE = 2\n"),
        (
            "def pytest_collection_modifyitems(items):\n    return None\n\nVALUE = 1\n",
            "def pytest_collection_modifyitems(items):\n    return None\n\nVALUE = 2\n",
        ),
    ],
    ids=["ordinary-app-edit", "unchanged-existing-hook"],
)
def test_generic_hook_scan_allows_unrelated_app_edits(
    pinned_text: str,
    patched_text: str,
    tmp_path: Path,
) -> None:
    tampered = _runner_config_tampering_for_test(
        tmp_path,
        config_files={},
        changed_path="pkg/app.py",
        pinned_text=pinned_text,
        patched_text=patched_text,
    )

    assert tampered == []


@pytest.mark.boundary
def test_generic_hook_scan_falls_back_to_added_lines_for_invalid_python(
    tmp_path: Path,
) -> None:
    path = "pkg/app.py"
    tampered = _runner_config_tampering_for_test(
        tmp_path,
        config_files={},
        changed_path=path,
        patched_text="VALUE = 2\n\ndef pytest_collection_modifyitems(:\n",
    )

    assert path in tampered


@pytest.mark.boundary
@pytest.mark.parametrize(
    "header",
    [
        'diff --git "a/conftest.py" b/conftest.py',
        'diff --git a/conftest.py "b/conftest.py"',
        '--- "a/conftest.py"',
        '+++ "b/conftest.py"',
        'rename from "a/conftest.py"',
        'rename to "b/conftest.py"',
        'copy from "a/conftest.py"',
        'copy to "b/conftest.py"',
    ],
)
def test_supported_diff_path_prefixes_reject_quoted_headers(header: str) -> None:
    from security_agents.tools.services import _supported_diff_path_prefixes

    if header.startswith("diff --git "):
        diff = f"{header}\nnew file mode 100644\n"
    else:
        diff = f"diff --git a/conftest.py b/conftest.py\n{header}\n"

    assert not _supported_diff_path_prefixes(diff)


@pytest.mark.boundary
def test_apply_fresh_rejects_quoted_headers_adding_root_conftest(
    intel: LocalIntel,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from security_agents.sandbox import workspace

    called = False

    def apply_quoted_diff(root: Path, _diff: str) -> tuple[bool, str]:
        nonlocal called
        called = True
        (root / "conftest.py").write_text("pytest_plugins = []\n", encoding="utf-8")
        return True, ""

    monkeypatch.setattr(workspace, "apply_diff", apply_quoted_diff)
    diff = (
        'diff --git "a/conftest.py" "b/conftest.py"\n'
        "new file mode 100644\n"
        "--- /dev/null\n"
        '+++ "b/conftest.py"\n'
        "@@ -0,0 +1 @@\n"
        "+pytest_plugins = []\n"
    )

    facts, _ = _apply_fresh_diff(intel, tmp_path, diff, plan_files=["conftest.py"])

    assert not facts["applied"]
    assert facts["apply_error"] == "unsupported diff path prefix"
    assert not called


@pytest.mark.boundary
def test_candidate_switch_cannot_reuse_a_later_patched_workspace(
    driver: LocalProcessDriver,
    library: CheckLibrary,
    tmp_path: Path,
) -> None:
    from security_agents.agents import verify as verify_agent
    from security_agents.sandbox.workspace import fresh_checkout, unified_diff
    from security_agents.tools import AuditSink, PatchApplier, ToolContext

    intel = _synthetic_test_target(tmp_path, tests_package=True)
    test_path = "tests/test_aaa.py"
    app_path = "pkg/app.py"
    bad_tree = fresh_checkout(intel.snapshot, tmp_path / "bad-source")
    (bad_tree / app_path).write_text("def value():\n    return 2\n", encoding="utf-8")
    (bad_tree / test_path).write_text(
        "from pkg.app import value\n\n\ndef test_regression() -> None:\n    assert value() == 1\n",
        encoding="utf-8",
    )
    good_tree = fresh_checkout(intel.snapshot, tmp_path / "good-source")
    (good_tree / test_path).write_text(
        "from pkg.app import value\n\n\ndef test_regression() -> None:\n    assert value() == 1\n",
        encoding="utf-8",
    )
    patcher = PatchApplier(
        intel=intel,
        artifacts={
            "bad": {
                "diff": unified_diff(intel.snapshot.root, bad_tree, [app_path, test_path]),
                "plan_files": [app_path],
                "tests_added": [test_path],
            },
            "good": {
                "diff": unified_diff(intel.snapshot.root, good_tree, [test_path]),
                "plan_files": [],
                "tests_added": [test_path],
            },
        },
        workdir=tmp_path / "apply",
    )
    ctx = ToolContext(
        assessment_id="asm_candidate_switch",
        agent=AgentName.VERIFY,
        run_id="run_candidate_switch",
        step_key="verify",
        read_root=intel.snapshot.root,
        audit=AuditSink(),
    )
    orch, _ = build(intel, driver, library, tmp_path, scripts={AgentName.PATCH: []})
    bad_facts = patcher.apply_fresh(ctx, "bad")
    assert bad_facts["applied"], bad_facts["apply_error"]
    bad_candidate = SimpleNamespace(id="bad", tests_added=[test_path])
    bad_added_runs_before_switch = orch._added_tests_on_patched(bad_candidate, ctx)
    assert bad_added_runs_before_switch and bad_added_runs_before_switch[0]["failed"] == 1

    good_facts = patcher.apply_fresh(ctx, "good")
    assert good_facts["applied"], good_facts["apply_error"]
    applied_patch_id = str(ctx.artifacts["verify_facts"]["patch_id"])
    assert applied_patch_id == "good"
    good_candidate = SimpleNamespace(id="good", tests_added=[test_path])
    bad_added_runs = orch._added_tests_on_patched(bad_candidate, ctx)
    assert bad_added_runs == []

    suite_runner = _synthetic_test_runner(intel, driver, library, tmp_path, isolated_suite=True)
    suite_run = suite_runner.run(ctx, "project_suite", [])
    assert suite_run["failed"] == 0, suite_run["stdout_tail"]
    assert suite_run["patch_id"] == applied_patch_id
    ctx.artifacts["tests_added"] = [test_path]
    good_added_runs = orch._added_tests_on_patched(good_candidate, ctx)
    assert good_added_runs and good_added_runs[0]["passed"] == 1

    def candidate_verdict(candidate_id: str, added_runs: list[dict[str, Any]]) -> str:
        evidence = verify_agent.VerifyEvidence(
            apply_facts=dict(ctx.artifacts["verify_facts"]),
            recheck_runs=[
                {
                    "template_ref": "check@1",
                    "matches_expectation": True,
                    "parameters": {},
                    "sandbox_run_id": "sbx_candidate_switch_check",
                }
            ],
            test_runs=[suite_run, *added_runs],
            baseline_failing=[],
            tests_added=[test_path],
            protected_tests=[],
            original_check_ref="check@1",
            original_check_params={},
            candidate_id=candidate_id,
        )
        return verify_agent.compute_verdict(evidence)[0]

    assert candidate_verdict("bad", bad_added_runs) == "rejected"
    assert candidate_verdict("good", good_added_runs) == "accepted"


@pytest.mark.boundary
@pytest.mark.parametrize(
    ("path", "original", "patched", "expected_tampered"),
    [
        (
            "tox.ini",
            "[pytest]\npython_files = test_*.py\n",
            "[pytest]\nPython_Files = test_*.py\n",
            True,
        ),
        (
            "tox.ini",
            "[testenv]\ncommands = pytest\n",
            "[testenv]\ncommands = pytest\n\n[pytest]\n",
            True,
        ),
        (
            "setup.cfg",
            "[options]\ninstall_requires = example\n",
            "[options]\ninstall_requires = example\n\n[tool:pytest]\n",
            True,
        ),
        (
            "tox.ini",
            "[testenv]\ncommands = pytest\n",
            "[testenv]\ncommands = pytest -q\n",
            False,
        ),
    ],
    ids=[
        "tox-option-case-change",
        "tox-empty-pytest-section",
        "setup-empty-pytest-section",
        "tox-testenv-only-change",
    ],
)
def test_runner_ini_comparison_preserves_case_and_section_presence(
    path: str,
    original: str,
    patched: str,
    expected_tampered: bool,
    tmp_path: Path,
) -> None:
    from security_agents.sandbox.workspace import unified_diff
    from security_agents.tools import PatchApplier

    snapshot_root = tmp_path / "snapshot"
    patched_root = tmp_path / "patched"
    snapshot_root.mkdir()
    patched_root.mkdir()
    for root, content in ((snapshot_root, original), (patched_root, patched)):
        config = root / path
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(content, encoding="utf-8")

    diff = unified_diff(snapshot_root, patched_root, [path])
    tampered = PatchApplier._tampered_runner_config(diff, snapshot_root, patched_root)

    assert (path in tampered) is expected_tampered


@pytest.mark.boundary
def test_orchestrator_protects_only_in_root_symlinked_tests(
    intel: LocalIntel, driver: LocalProcessDriver, library: CheckLibrary, tmp_path: Path
) -> None:
    orch, _ = build(intel, driver, library, tmp_path)
    tests_root = intel.snapshot.root / "tests"
    safe_link = tests_root / "test_safe_link.py"
    safe_link.symlink_to("../build_recipe.json")
    outside_target = tmp_path / "outside_test.py"
    outside_target.write_text("outside\n")
    outside_link = tests_root / "test_outside_link.py"
    outside_link.symlink_to(outside_target)

    protected = orch._protected_tests()

    assert "tests/test_safe_link.py" in protected
    assert "tests/test_outside_link.py" not in protected

    dangling_link = tests_root / "test_dangling_link.py"
    dangling_link.symlink_to("missing_test_target.py")
    protected = orch._protected_tests()
    assert "tests/test_dangling_link.py" not in protected
    assert any("protected-test discovery failed: SNAPSHOT_NOT_READY" in path for path in protected)


def test_tampered_tests_flags_addition_only_changes() -> None:
    from security_agents.tools import PatchApplier

    diff = """diff --git a/tests/test_api.py b/tests/test_api.py
index 1234567..89abcde 100644
--- a/tests/test_api.py
+++ b/tests/test_api.py
@@ -1,1 +1,2 @@
 existing
+def test_bypass(): pass
"""
    assert PatchApplier._tampered_tests(diff, ["tests/test_api.py"]) == ["tests/test_api.py"]


def test_tampered_tests_skips_traversal_header_and_flags_later_protected_section() -> None:
    from security_agents.tools import PatchApplier

    diff = """diff --git a/../x b/../x
@@ -1 +1 @@
-before
+after
diff --git a/tests/test_api.py b/tests/test_api.py
index 1234567..89abcde 100644
--- a/tests/test_api.py
+++ b/tests/test_api.py
@@ -1,1 +1,2 @@
 existing
+def test_bypass(): pass
"""
    assert PatchApplier._tampered_tests(diff, ["tests/test_api.py"]) == ["tests/test_api.py"]


def test_tampered_tests_flags_plain_unified_diff_and_apply_diff_accepts_it(
    tmp_path: Path,
) -> None:
    from security_agents.sandbox.workspace import apply_diff
    from security_agents.tools import PatchApplier

    diff = """--- a/tests/test_api.py
+++ b/tests/test_api.py
@@ -1 +1 @@
-before
+after
"""
    assert PatchApplier._tampered_tests(diff, ["tests/test_api.py"]) == ["tests/test_api.py"]
    root = tmp_path / "repo"
    target = root / "tests" / "test_api.py"
    target.parent.mkdir(parents=True)
    target.write_text("before\n")
    applied, error = apply_diff(root, diff)
    assert applied, error
    assert target.read_text() == "after\n"


def test_tampered_tests_flags_rename_on_either_protected_path() -> None:
    from security_agents.tools import PatchApplier

    diff = """diff --git a/tests/test_api.py b/tests/test_renamed.py
similarity index 100%
rename from tests/test_api.py
rename to tests/test_renamed.py
"""
    assert PatchApplier._tampered_tests(diff, ["tests/test_api.py"]) == ["tests/test_api.py"]
    assert PatchApplier._tampered_tests(diff, ["tests/test_renamed.py"]) == ["tests/test_renamed.py"]


@pytest.mark.parametrize(
    "metadata",
    [
        "copy from tests/test_api.py\ncopy to tests/test_copy.py",
        "Binary files a/tests/test_api.py and b/tests/test_api.py differ",
        "GIT binary patch",
    ],
)
def test_tampered_tests_flags_copy_and_binary_metadata(metadata: str) -> None:
    from security_agents.tools import PatchApplier

    diff = f"diff --git a/tests/test_api.py b/tests/test_copy.py\n{metadata}\n"
    assert PatchApplier._tampered_tests(diff, ["tests/test_api.py"]) == ["tests/test_api.py"]
    assert PatchApplier._tampered_tests(diff, ["tests/test_copy.py"]) == ["tests/test_copy.py"]


def test_tampered_tests_flags_deletion() -> None:
    from security_agents.tools import PatchApplier

    diff = """diff --git a/tests/test_api.py b/tests/test_api.py
deleted file mode 100644
index 1234567..0000000
--- a/tests/test_api.py
+++ /dev/null
@@ -1 +0,0 @@
-existing
"""
    assert PatchApplier._tampered_tests(diff, ["tests/test_api.py"]) == ["tests/test_api.py"]


def test_tampered_tests_does_not_flag_a_new_test_file() -> None:
    from security_agents.tools import PatchApplier

    diff = """diff --git a/tests/test_new_case.py b/tests/test_new_case.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/tests/test_new_case.py
@@ -0,0 +1 @@
+def test_new_case(): pass
"""
    assert PatchApplier._tampered_tests(diff, ["tests/test_new_case.py"]) == []


def test_tampered_test_content_check_flags_changes_and_allows_equal_bytes(tmp_path: Path) -> None:
    from security_agents.tools import PatchApplier

    snapshot_root = tmp_path / "snapshot"
    patched_root = tmp_path / "patched"
    original = snapshot_root / "tests" / "test_api.py"
    patched = patched_root / "tests" / "test_api.py"
    original.parent.mkdir(parents=True)
    patched.parent.mkdir(parents=True)
    original.write_bytes(b"original bytes\n")
    patched.write_bytes(b"changed bytes\n")

    assert PatchApplier._tampered_test_contents(snapshot_root, patched_root, ["tests/test_api.py"]) == [
        "tests/test_api.py"
    ]

    patched.write_bytes(b"original bytes\n")
    assert PatchApplier._tampered_test_contents(snapshot_root, patched_root, ["tests/test_api.py"]) == []

    patched.unlink()
    assert PatchApplier._tampered_test_contents(snapshot_root, patched_root, ["tests/test_api.py"]) == [
        "tests/test_api.py"
    ]

    original.unlink()
    assert PatchApplier._tampered_test_contents(snapshot_root, patched_root, ["tests/test_api.py"]) == []


def test_tampered_test_content_check_flags_escaping_patched_symlink(tmp_path: Path) -> None:
    from security_agents.tools import PatchApplier

    snapshot_root = tmp_path / "snapshot"
    patched_root = tmp_path / "patched"
    original = snapshot_root / "tests" / "test_api.py"
    patched = patched_root / "tests" / "test_api.py"
    original.parent.mkdir(parents=True)
    patched.parent.mkdir(parents=True)
    original.write_bytes(b"original bytes\n")
    outside = tmp_path / "outside.py"
    outside.write_bytes(b"external bytes\n")
    patched.symlink_to(outside)

    assert PatchApplier._tampered_test_contents(snapshot_root, patched_root, ["tests/test_api.py"]) == [
        "tests/test_api.py"
    ]


@pytest.mark.parametrize(
    ("snapshot_entry", "patched_entry", "expected"),
    [
        ("dangling-symlink", "file", ["tests/test_x.py"]),
        ("directory", "file", ["tests/test_x.py"]),
        ("escaping-symlink", "file", ["tests/test_x.py"]),
        ("absent", "file", []),
        ("absent", "escaping-symlink", ["tests/test_x.py"]),
    ],
)
def test_tampered_test_content_check_handles_snapshot_entry_types(
    snapshot_entry: str,
    patched_entry: str,
    expected: list[str],
    tmp_path: Path,
) -> None:
    from security_agents.tools import PatchApplier

    path = "tests/test_x.py"
    snapshot_root = tmp_path / "snapshot"
    patched_root = tmp_path / "patched"
    snapshot_path = snapshot_root / path
    patched_path = patched_root / path
    snapshot_path.parent.mkdir(parents=True)
    patched_path.parent.mkdir(parents=True)
    outside = tmp_path / "outside.py"
    outside.write_text("outside\n", encoding="utf-8")

    if snapshot_entry == "dangling-symlink":
        snapshot_path.symlink_to("missing.py")
    elif snapshot_entry == "directory":
        snapshot_path.mkdir()
    elif snapshot_entry == "escaping-symlink":
        snapshot_path.symlink_to(outside)

    if patched_entry == "file":
        patched_path.write_text("test\n", encoding="utf-8")
    elif patched_entry == "escaping-symlink":
        patched_path.symlink_to(outside)

    assert PatchApplier._tampered_test_contents(snapshot_root, patched_root, [path]) == expected


@pytest.mark.boundary
def test_verify_rejects_a_planted_bad_patch_that_edits_a_protected_test(intel, driver, library, tmp_path):
    """A diff authored outside the worktree guard is still rejected by Verify (SB-09).

    This is the `examples/fixtures/bad-patches` case: a patch that makes the
    failing expectation pass by weakening the test that encodes it.
    """
    from security_agents.agents import verify as verify_agent
    from security_agents.sandbox.workspace import fresh_checkout, unified_diff
    from security_agents.tools import AuditSink, PatchApplier, ToolContext

    recipe_path = intel.snapshot.root / "build_recipe.json"
    recipe_path.chmod(0o644)
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    recipe["protected_tests"] = ["tests/test_api.py"]
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
    recipe_path.chmod(0o444)
    orchestrator, _ = build(intel, driver, library, tmp_path)
    protected_tests = orchestrator._protected_tests()
    assert "tests/test_api.py" in protected_tests

    work = tmp_path / "bad"
    wt = fresh_checkout(intel.snapshot, work / "wt")
    protected = wt / "tests" / "test_api.py"
    protected.write_text(protected.read_text().replace("== 404", "in (200, 404)"))
    diff = unified_diff(intel.snapshot.root, wt, ["tests/test_api.py"])
    assert "tests/test_api.py" in diff

    applier = PatchApplier(
        intel=intel,
        artifacts={
            "pat_bad": {
                "diff": diff,
                "plan_files": ["payments_lite/app.py"],
                "protected_tests": protected_tests,
            }
        },
        workdir=work,
    )
    ctx = ToolContext(
        assessment_id="asm_bad",
        agent=AgentName.VERIFY,
        run_id="run_bad",
        step_key="verify",
        read_root=intel.snapshot.root,
        audit=AuditSink(),
    )
    facts = applier.apply_fresh(ctx, "pat_bad")
    assert facts["applied"] is True
    assert facts["tampered_protected_tests"] == ["tests/test_api.py"]
    # editing an existing test is both tampering and outside the plan's file set
    assert facts["out_of_scope_files"] == ["tests/test_api.py"]
    assert facts["new_test_files"] == []

    evidence = verify_agent.VerifyEvidence(
        apply_facts=dict(ctx.artifacts["verify_facts"]),
        recheck_runs=[],
        test_runs=[],
        baseline_failing=[],
        tests_added=[],
        protected_tests=protected_tests,
        original_check_ref="access_control.ownership@1",
        original_check_params={},
        candidate_id="pat_bad",
    )
    verdict, checks, reasons = verify_agent.compute_verdict(evidence)
    assert verdict == "rejected"
    assert not next(c for c in checks if c.name.value == "no_test_tampering").passed
    assert not next(c for c in checks if c.name.value == "diff_scope_ok").passed
    assert any("tests/test_api.py" in r for r in reasons)


@pytest.mark.boundary
def test_verify_rejects_a_planted_bad_patch_outside_the_plan(intel, driver, library, tmp_path):
    from security_agents.agents import verify as verify_agent
    from security_agents.sandbox.workspace import fresh_checkout, unified_diff
    from security_agents.tools import AuditSink, PatchApplier, ToolContext

    work = tmp_path / "bad2"
    wt = fresh_checkout(intel.snapshot, work / "wt")
    store = wt / "payments_lite" / "store.py"
    store.write_text(store.read_text() + "\n# unrelated change\n")
    diff = unified_diff(intel.snapshot.root, wt, ["payments_lite/store.py"])

    applier = PatchApplier(
        intel=intel,
        artifacts={
            "pat_scope": {
                "diff": diff,
                "plan_files": ["payments_lite/app.py"],
                "protected_tests": ["tests/test_api.py"],
            }
        },
        workdir=work,
    )
    ctx = ToolContext(
        assessment_id="asm_bad2",
        agent=AgentName.VERIFY,
        run_id="run_bad2",
        step_key="verify",
        read_root=intel.snapshot.root,
        audit=AuditSink(),
    )
    facts = applier.apply_fresh(ctx, "pat_scope")
    assert facts["out_of_scope_files"] == ["payments_lite/store.py"]
    verdict, checks, _ = verify_agent.compute_verdict(
        verify_agent.VerifyEvidence(
            apply_facts=dict(ctx.artifacts["verify_facts"]),
            recheck_runs=[],
            test_runs=[],
            baseline_failing=[],
            tests_added=[],
            protected_tests=["tests/test_api.py"],
            original_check_ref="access_control.ownership@1",
            original_check_params={},
            candidate_id="pat_scope",
        )
    )
    assert verdict == "rejected"
    assert not next(c for c in checks if c.name.value == "diff_scope_ok").passed


@pytest.mark.boundary
def test_patch_without_a_regression_test_is_rejected(intel, driver, library, tmp_path):
    """A fix with no test is not verifiable, so it cannot be accepted."""
    orch, _ = build(intel, driver, library, tmp_path, skip_tests=True)
    res = orch.run()
    finding = res.findings[0]
    assert finding.verifications
    generated = next(c for c in finding.verifications[0].checks if c.name.value == "generated_tests_pass")
    assert not generated.passed
    assert finding.verifications[0].verdict == "rejected"


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
    order = [r.agent.value for r in res.runs]
    assert order[:2] == ["scout", "probe"] and sorted(order[2:]) == ["diagnose", "trace"], order
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
            project_id="prj_test",
            subject_type="remediation",
            subject_id=finding.plan.id if finding.plan else "x",
            decision="approved",
            decided_by="agent:patch",
        )

    config = OrchestratorConfig(
        assessment_id="asm_gate",
        project_id="prj_test",
        org_id="org_test",
        scope=live_scope(),
        target_id=TARGET_ID,
        requested_by="usr_requester",
    )
    res = Orchestrator(
        config,
        intel=intel,
        gateway=gateway,
        driver=driver,
        library=library,
        workdir=tmp_path / "w",
        approve_remediation=agent_approver,
    ).run()
    assert not any(r.agent is AgentName.PATCH for r in res.runs)
    assert "approval.invalid_actor" in [e.action for e in res.audit]


def test_approval_for_a_different_plan_is_ignored(intel, driver, library, tmp_path):
    scripts = fake_agents.all_scripts(intel.snapshot.root)
    gateway = ProviderGateway(FakeLLM(scripts))

    def wrong_approver(finding: FindingRecord) -> Approval | None:
        return Approval(
            project_id="prj_test",
            subject_type="remediation",
            subject_id="rmp_someone_else",
            decision="approved",
            decided_by="usr_human",
        )

    config = OrchestratorConfig(
        assessment_id="asm_gate2",
        project_id="prj_test",
        org_id="org_test",
        scope=live_scope(),
        target_id=TARGET_ID,
        requested_by="usr_requester",
    )
    res = Orchestrator(
        config,
        intel=intel,
        gateway=gateway,
        driver=driver,
        library=library,
        workdir=tmp_path / "w",
        approve_remediation=wrong_approver,
    ).run()
    assert not any(r.agent is AgentName.PATCH for r in res.runs)
    assert "approval.mismatch" in [e.action for e in res.audit]


def test_finding_standards_are_evidence_backed(result):
    """One planted IDOR finding, classified from executed evidence (not an LLM score)."""
    res, _ = result
    finding = res.findings[0]
    std = finding.standards
    assert std is not None
    assert std.cwe and std.cwe.id == "CWE-639"
    assert "T1190" in [m.id for m in std.attack]
    assert std.cvss and std.cvss.complete and std.cvss.score is not None
    assert "provisional" not in std.cvss.assessor
    assert std.exploit_status.value == "reproduced_in_sandbox"
    summary = finding.public()["standards"]
    assert summary["cwe"] == "CWE-639"
    assert summary["cvss_complete"] is True
    assert "D3-AMED" in [m.id for m in std.d3fend]


# --- functional remediation approvals owed by the host (Srihith follow-up on #73) ---


def test_pending_functional_approval_pauses_even_with_approved_security_work(
    intel, driver, library, tmp_path
):
    orch, _ = build(intel, driver, library, tmp_path)  # security remediation approved
    orch.external_pending = lambda: True
    res = orch.run()
    assert res.state is AssessmentState.AWAITING_APPROVAL
    assert "patch" not in [r.agent.value for r in res.runs], "nothing remediated before all decide"


def test_early_security_exit_still_waits_for_a_functional_approval(intel, driver, library, tmp_path):
    from security_agents.agents import scout as scout_agent
    from security_agents.llm import FakeTurn

    submit = scout_agent.SPEC.submit_tool_name()
    empty = {
        "hypotheses": [],
        "coverage": {"entry_points_reviewed": [], "looks_correct": [], "skipped_with_reason": []},
        "suspicious_instructions": [],
    }
    scripts = fake_agents.all_scripts(intel.snapshot.root)
    scripts[AgentName.SCOUT] = [FakeTurn(tool_calls=[(submit, empty)])]
    orch, _ = build(intel, driver, library, tmp_path, scripts=scripts)
    orch.external_pending = lambda: True
    res = orch.run()
    assert res.state is AssessmentState.AWAITING_APPROVAL
    skipped = [e for e in res.state_log.entries if "skipped (no hypotheses)" in e[2]]
    assert len(skipped) == 4, res.state_log  # VALIDATION, ANALYSIS, DIAGNOSIS, AWAITING_APPROVAL

    orch2, _ = build(intel, driver, library, tmp_path / "b", scripts=scripts)
    assert orch2.run().state is AssessmentState.COMPLETED  # nothing owed: report as before


def test_report_carries_a_bounded_redacted_tool_trace_per_run(result):
    """A failed paid live run must be diagnosable from the report (M3 attempt: Probe was
    inconclusive and the report had only counts)."""
    report = result[0].report()
    for run in report["runs"]:
        trace = run["tool_trace"]
        assert len(trace) == run["tool_calls"] or len(trace) == 40, run["agent"]
        assert trace, f"{run['agent']} has no tool trace"
        for call in trace:
            assert set(call) == {"name", "ok", "error_code", "args", "summary"}
            assert len(call["args"]) <= 800 and len(call["summary"]) <= 1200
    probe = next(r for r in report["runs"] if r["agent"] == "probe")
    checks = [c for c in probe["tool_trace"] if c["name"] == "checks.run_template" and c["ok"]]
    assert checks, probe["tool_trace"]
    # A SUCCESSFUL check keeps its outcome, so an inconclusive live Probe is diagnosable.
    summary = json.loads(checks[-1]["summary"])
    assert "matches_expectation" in summary and "exit_code" in summary, summary
    assert "route_id" in json.loads(checks[-1]["args"])["parameters"]
