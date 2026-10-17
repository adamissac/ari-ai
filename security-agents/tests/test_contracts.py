"""Contract tests: every record the security pillar publishes validates against `shared`.

These run against the real canonical package (`shared`, owner Srihith). If a
contract changes, these fail here rather than at the API boundary. They also
pin the mapping gaps that were reported to the contract owner, so a fix on
either side shows up as a test change.
"""

from __future__ import annotations

import json

import pytest

from security_agents.contracts import export

shared = pytest.importorskip("shared", reason="canonical shared package not importable")
import shared.assessment as shared_assessment  # noqa: E402
import shared.findings as shared_findings  # noqa: E402

from . import fake_agents  # noqa: E402
from .conftest import TARGET_ID, live_scope  # noqa: E402


def test_mapped_models_have_not_drifted():
    """A change to a model this adapter maps must fail here, not at the API edge.

    This is deliberately structural rather than a version pin: `shared` bumps
    its SCHEMA_VERSION for changes all over the contract surface, and only the
    models listed in `export.MAPPED_FIELDS` affect the security pillar.
    """
    assert export.schema_version() == shared.SCHEMA_VERSION
    drift = export.mapping_drift()
    assert drift == [], (
        "canonical contracts moved under the adapter; review the mappings in "
        f"security_agents/contracts/export.py: {drift}"
    )
    export.assert_supported_schema()


def test_version_is_one_we_verified_against():
    """Informational: a new version passes only while the mapped models match."""
    if shared.SCHEMA_VERSION not in export.VERIFIED_SCHEMA_VERSIONS:
        pytest.skip(
            f"shared {shared.SCHEMA_VERSION} is newer than the versions this adapter was "
            f"verified against {export.VERIFIED_SCHEMA_VERSIONS}; the structural check above "
            "is what gates correctness"
        )
    assert export.mapping_drift() == []


def test_drift_is_detected_when_a_mapped_field_changes(monkeypatch):
    """The drift check must actually catch a change (guard against a no-op test)."""
    monkeypatch.setitem(
        export.MAPPED_FIELDS, ("findings", "Hypothesis"),
        {**export.MAPPED_FIELDS[("findings", "Hypothesis")], "title": True},
    )
    drift = export.mapping_drift()
    assert any("title" in problem for problem in drift)
    with pytest.raises(export.ContractUnavailable):
        export.assert_mappings_current()


@pytest.fixture(scope="module")
def completed(request):
    """One full assessment, reused by every mapping test in this module."""
    from security_agents.contracts import Approval, Budget
    from security_agents.intel import load_expectations
    from security_agents.llm import FakeLLM, ProviderGateway
    from security_agents.sandbox.driver import LocalProcessDriver
    from security_agents.sandbox.workspace import SnapshotHandle, copy_tree
    from security_agents.workflow import Orchestrator, OrchestratorConfig

    from .conftest import BUILD_RECIPE, LABELS, PAYMENTS_LITE

    tmp = request.getfixturevalue("tmp_path_factory").mktemp("contracts")
    staging = tmp / "staging"
    copy_tree(PAYMENTS_LITE, staging)
    import shutil

    shutil.copy2(BUILD_RECIPE, staging / "build_recipe.json")
    snapshot = SnapshotHandle.from_directory(
        staging, tmp / "snapshot", snapshot_id="snp_contract", repo_id="rep_payments_lite"
    )
    from security_agents.checks.library import default_library
    from security_agents.intel import LocalIntel

    intel = LocalIntel(
        snapshot,
        expectations=load_expectations(
            LABELS, snapshot_id=snapshot.snapshot_id, commit_sha=snapshot.commit_sha,
            strip_prefix="target/",
        ),
    )
    gateway = ProviderGateway(FakeLLM(fake_agents.all_scripts(snapshot.root)))
    config = OrchestratorConfig(
        assessment_id="asm_contract", project_id="prj_contract", org_id="org_contract",
        scope=live_scope(), target_id=TARGET_ID, requested_by="usr_requester",
        budget=Budget(max_tokens=2_000_000, max_usd=50.0, max_wall_clock_s=900.0),
    )
    result = Orchestrator(
        config, intel=intel, gateway=gateway, driver=LocalProcessDriver(allow=True),
        library=default_library(), workdir=tmp / "work",
        approve_remediation=lambda f: Approval(
            project_id="prj_contract", subject_type="remediation", subject_id=f.plan.id,
            decision="approved", decided_by="usr_human",
        ),
    ).run()
    assert result.findings and result.findings[0].verifications, "fixture assessment did not complete"
    return result, intel


def test_expectation_ids_are_mapped_deterministically():
    """Pinned gap 5: human-readable expectation ids do not match the canonical pattern."""
    raw = "exp_owner_only"
    mapped = export.canonical_expectation_id(raw)
    assert mapped != raw
    assert mapped.startswith("exp_") and mapped[4:].isalnum()
    assert export.canonical_expectation_id(raw) == mapped, "mapping must be deterministic"
    # an id that already conforms is untouched
    assert export.canonical_expectation_id("exp_01ABCDEFGH") == "exp_01ABCDEFGH"
    notes = export.expectation_id_notes([raw, "exp_01ABCDEFGH"])
    assert notes == {raw: mapped}, "only remapped ids are reported"


def test_confidence_is_mapped_to_a_number():
    """Pinned gap 6: `shared` expresses confidence numerically."""
    from security_agents.contracts import Confidence

    scores = [export.CONFIDENCE_SCORE[c] for c in (Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH)]
    assert scores == sorted(scores)
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_long_agent_text_is_truncated_not_rejected(completed):
    """Pinned gap 3: ShortText caps the agent's reasoning at 500 characters."""
    result, _ = completed
    finding = result.findings[0]
    exported = export.hypothesis(finding.hypothesis, finding_id=finding.finding_id)
    assert len(exported.rationale) <= export.SHORT_TEXT_MAX

    # A longer rationale (agents routinely write more than 500 characters) is
    # truncated rather than rejected, and the full text stays internal.
    verbose = finding.hypothesis.model_copy(
        update={"rationale": finding.hypothesis.rationale + " " + "detail. " * 100}
    )
    exported_verbose = export.hypothesis(verbose, finding_id=finding.finding_id)
    assert len(verbose.rationale) > export.SHORT_TEXT_MAX
    assert len(exported_verbose.rationale) <= export.SHORT_TEXT_MAX
    assert exported_verbose.rationale.endswith("...")


def test_hypothesis_exports(completed):
    result, _ = completed
    finding = result.findings[0]
    exported = export.hypothesis(finding.hypothesis, finding_id=finding.finding_id)
    assert isinstance(exported, shared_findings.Hypothesis)
    assert exported.weakness_class == "CWE-639"
    assert exported.cited_spans[0].kind is shared.evidence.EvidenceKind.source_span
    assert exported.cited_spans[0].commit_sha
    # the internal title is preserved at the head of rationale (gap 3)
    assert exported.rationale.startswith(finding.hypothesis.title[:40])
    assert exported.confidence == export.CONFIDENCE_SCORE[finding.hypothesis.confidence]
    assert all(e.startswith("exp_") for e in exported.expectation_ids)
    json.loads(exported.model_dump_json())


def test_validation_result_exports_with_executed_evidence(completed):
    result, _ = completed
    validation = result.findings[0].validation
    exported = export.validation_result(validation)
    assert isinstance(exported, shared_findings.ValidationResult)
    assert exported.outcome is shared_findings.ValidationOutcome.confirmed
    assert exported.check_template_id == "access_control.ownership"
    assert exported.sandbox_run_id
    assert exported.evidence[0].kind is shared.evidence.EvidenceKind.sandbox_run
    assert exported.evidence[0].sha256


def test_inconclusive_validation_cannot_be_expressed(completed):
    """Pinned gap 1: the canonical model has no shape for 'no run happened'."""
    from security_agents.contracts import ValidationOutcome, ValidationResult

    unexecuted = ValidationResult(
        hypothesis_id="hyp_01ABCDEFGH", outcome=ValidationOutcome.INCONCLUSIVE,
        check_template_id=None, check_template_version=None, sandbox_run_id=None,
    )
    with pytest.raises(ValueError, match="requires an executed check"):
        export.validation_result(unexecuted)


def test_attack_path_and_severity_export(completed):
    result, _ = completed
    finding = result.findings[0]
    path = export.attack_path(finding.attack_path)
    severity = export.severity(finding.severity)
    assert isinstance(path, shared_findings.AttackPath)
    assert [s.order for s in path.steps] == list(range(1, len(path.steps) + 1))
    assert isinstance(severity, shared_findings.SeverityAssessment)
    assert severity.level is shared_findings.SeverityLevel.medium
    assert severity.factors.verified_path is True
    verified = [s for s in path.steps if s.verified]
    assert verified and all(s.evidence for s in verified)


def test_root_cause_and_plan_export(completed):
    result, _ = completed
    finding = result.findings[0]
    rc = export.root_cause(finding.root_cause)
    plan = export.remediation_plan(finding.plan)
    assert isinstance(rc, shared_findings.RootCause)
    assert rc.cause_class == "missing_check"
    assert isinstance(plan, shared_findings.RemediationPlan)
    assert plan.files_expected == ["payments_lite/app.py"]
    # gap 2: the structured test plan is flattened into one text field
    assert "must fail before:" in plan.test_plan and "must pass after:" in plan.test_plan


def test_patch_candidate_exports(completed):
    result, intel = completed
    finding = result.findings[0]
    candidate = finding.candidates[-1]
    patch_run = next(r for r in result.runs if r.agent.value == "patch")
    exported = export.patch_candidate(
        candidate,
        base_commit_sha=intel.snapshot.commit_sha,
        produced_by_run_id=patch_run.id,
        rationale="added the missing ownership check",
    )
    assert isinstance(exported, shared_findings.PatchCandidate)
    assert exported.diff_sha256 == candidate.diff_sha256
    assert exported.base_commit_sha == intel.snapshot.commit_sha
    assert exported.produced_by_run_id == patch_run.id
    assert "payments_lite/app.py" in exported.files_changed


def test_verification_result_exports_and_enforces_the_accept_rule(completed):
    result, _ = completed
    finding = result.findings[0]
    verify_run = next(r for r in result.runs if r.agent.value == "verify")
    exported = export.verification_result(
        finding.verifications[-1], produced_by_run_id=verify_run.id
    )
    assert isinstance(exported, shared_findings.VerificationResult)
    assert exported.verdict is shared_findings.VerificationVerdict.accepted
    assert len(exported.checks) == 5
    assert all(c.evidence for c in exported.checks), "every check must cite evidence"
    assert exported.sandbox_run_ids


def test_canonical_model_rejects_accepted_with_a_failing_check(completed):
    """`shared` enforces the same rule our verdict function does — double lock."""
    result, _ = completed
    verify_run = next(r for r in result.runs if r.agent.value == "verify")
    internal = result.findings[0].verifications[-1].model_copy(deep=True)
    internal.checks[0].passed = False
    with pytest.raises(Exception, match="accepted verdict requires"):
        export.verification_result(internal, produced_by_run_id=verify_run.id)


def test_rejected_verification_exports(intel, tmp_path):
    """A rejected verdict with no executed run still produces a valid record."""
    from security_agents.agents import verify as verify_agent

    evidence = verify_agent.VerifyEvidence(
        apply_facts={"applied": False, "files_touched": [], "out_of_scope": [], "new_tests": [],
                     "tampered_protected_tests": []},
        recheck_runs=[], test_runs=[], baseline_failing=[], tests_added=[], protected_tests=[],
        original_check_ref="access_control.ownership@1", original_check_params={},
    )
    data = verify_agent.VerifyInput(
        assessment_id="asm_x", patch_id="pat_01ABCDEFGH", finding_id="fnd_01ABCDEFGH",
        remediation_plan_id="rmp_01ABCDEFGH", scope_id="scp_01ABCDEFGH", target_id=TARGET_ID,
    )
    internal = verify_agent.to_result(
        None, data, evidence, sandbox_run_ids=[], verify_run_id="run_01ABCDEFGH"
    )
    exported = export.verification_result(internal, produced_by_run_id="run_01ABCDEFGH")
    assert exported.verdict is shared_findings.VerificationVerdict.rejected
    assert all(c.evidence for c in exported.checks)
    assert exported.reasons


def test_agent_runs_export_with_tool_call_records(completed):
    result, _ = completed
    for run, record in zip(result.runs, result.records, strict=True):
        tool_calls = [
            {"name": t.name, "args": t.args, "ok": t.ok, "error_code": t.error_code, "turn": i}
            for i, t in enumerate(record.tool_invocations)
        ]
        exported = export.agent_run(run, tool_calls=tool_calls)
        assert isinstance(exported, shared_assessment.AgentRun)
        assert exported.provider_mode == "fake", "provider mode must stay honest on the wire"
        assert exported.status is shared_assessment.AgentRunStatus.succeeded
        assert exported.usage.llm_calls == run.llm_turns
        assert len(exported.tool_calls) == len(tool_calls)
        json.loads(exported.model_dump_json())


def test_denied_tool_calls_are_reported_as_denied(intel):
    """A refused tool must not look like a generic error on the wire."""
    from security_agents.contracts import AgentName, AgentRun, ErrorCode

    run = AgentRun(
        assessment_id="asm_01ABCDEFGH", agent=AgentName.SCOUT, step_key="recon", status="succeeded",
        input_ref="x", model_id="claude-opus-5-5", provider_mode="fake",
    )
    exported = export.agent_run(
        run,
        tool_calls=[
            {"name": "checks.run_template", "args": {}, "ok": False,
             "error_code": ErrorCode.TOOL_NOT_ALLOWED.value, "turn": 0},
            {"name": "code.search", "args": {"pattern": "x"}, "ok": True, "error_code": None, "turn": 1},
        ],
    )
    outcomes = [c.outcome.value for c in exported.tool_calls]
    assert outcomes == ["denied", "ok"]
    assert exported.tool_calls[0].error_code.value == ErrorCode.TOOL_NOT_ALLOWED.value


def test_every_exported_model_round_trips_through_json(completed):
    result, intel = completed
    finding = result.findings[0]
    verify_run = next(r for r in result.runs if r.agent.value == "verify")
    patch_run = next(r for r in result.runs if r.agent.value == "patch")
    exported = [
        export.hypothesis(finding.hypothesis, finding_id=finding.finding_id),
        export.validation_result(finding.validation),
        export.attack_path(finding.attack_path),
        export.root_cause(finding.root_cause),
        export.remediation_plan(finding.plan),
        export.patch_candidate(
            finding.candidates[-1], base_commit_sha=intel.snapshot.commit_sha,
            produced_by_run_id=patch_run.id, rationale="fix",
        ),
        export.verification_result(finding.verifications[-1], produced_by_run_id=verify_run.id),
    ]
    for model in exported:
        payload = json.loads(model.model_dump_json())
        again = type(model).model_validate(payload)
        assert again == model
