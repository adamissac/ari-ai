"""Tier 0/1 contract tests: roundtrip, strictness, state machine, codegen freshness, TS compile."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from shared import examples, export
from shared.assessment import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    AssessmentState,
    can_transition,
)
from shared.audit import GENESIS_HASH, audit_hash
from shared.evidence import EvidenceKind, EvidenceRef
from shared.findings import VerificationResult
from shared.ids import IdPrefix, new_id
from shared.registry import BY_NAME, MODELS

FIXTURES = sorted(examples.FIXTURE_DIR.glob("*.json"))


def test_every_registered_model_builds_a_json_schema() -> None:
    for model in MODELS:
        schema = model.model_json_schema()
        assert schema["type"] == "object", model.__name__
        assert schema.get("additionalProperties") is False, f"{model.__name__} must forbid extras"


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_fixture_roundtrips_exactly(path: Path) -> None:
    model = BY_NAME[path.stem]
    raw = json.loads(path.read_text())
    obj = model.model_validate_json(path.read_text())
    assert obj.model_dump(mode="json") == raw
    assert model.model_validate(obj.model_dump(mode="json")) == obj


def test_fixtures_cover_core_handoffs() -> None:
    names = {p.stem for p in FIXTURES}
    for required in (
        "ContextPack",
        "Finding",
        "PatchCandidate",
        "VerificationResult",
        "AgentRun",
        "MonitoringEvent",
        "ReassessmentRequest",
        "DefenseRecommendation",
        "StreamEvent",
    ):
        assert required in names


def test_unknown_field_rejected() -> None:
    raw = json.loads((examples.FIXTURE_DIR / "Finding.json").read_text())
    raw["invented_by_llm"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BY_NAME["Finding"].model_validate(raw)


def test_unsupported_enum_rejected() -> None:
    raw = json.loads((examples.FIXTURE_DIR / "Finding.json").read_text())
    raw["status"] = "probably_fine"
    with pytest.raises(ValidationError):
        BY_NAME["Finding"].model_validate(raw)


def test_naive_and_non_utc_timestamps_rejected() -> None:
    raw = json.loads((examples.FIXTURE_DIR / "Assessment.json").read_text())
    raw["created_at"] = "2026-10-17T01:00:00"
    with pytest.raises(ValidationError, match="timezone-aware"):
        BY_NAME["Assessment"].model_validate(raw)
    raw["created_at"] = datetime(2026, 10, 17, tzinfo=timezone(timedelta(hours=-4))).isoformat()
    with pytest.raises(ValidationError, match="UTC"):
        BY_NAME["Assessment"].model_validate(raw)


def test_short_sha_and_wrong_id_prefix_rejected() -> None:
    raw = json.loads((examples.FIXTURE_DIR / "Assessment.json").read_text())
    with pytest.raises(ValidationError):
        BY_NAME["Assessment"].model_validate({**raw, "commit_sha": "abc1234"})
    with pytest.raises(ValidationError):
        BY_NAME["Assessment"].model_validate({**raw, "project_id": raw["scope_id"]})


def test_source_span_evidence_must_be_pinned() -> None:
    with pytest.raises(ValidationError, match="requires path, commit_sha and span"):
        EvidenceRef(kind=EvidenceKind.source_span, path="app/x.py", provenance="t")
    with pytest.raises(ValidationError, match="artifact_id and sha256"):
        EvidenceRef(kind=EvidenceKind.test_run, provenance="t")


@pytest.mark.parametrize("bad", ["/etc/passwd", "../secrets", "a/../../b", "a\\b"])
def test_repo_paths_must_be_relative(bad: str) -> None:
    with pytest.raises(ValidationError):
        EvidenceRef(kind=EvidenceKind.doc, path=bad, provenance="t")


def test_verify_cannot_accept_with_failed_check() -> None:
    raw = json.loads((examples.FIXTURE_DIR / "VerificationResult.json").read_text())
    raw["checks"][0]["passed"] = False
    with pytest.raises(ValidationError, match="every verification check"):
        VerificationResult.model_validate(raw)


def test_state_machine_shape() -> None:
    assert can_transition(AssessmentState.CREATED, AssessmentState.SCOPE_CHECK)
    assert not can_transition(AssessmentState.CREATED, AssessmentState.REMEDIATION)
    assert not can_transition(AssessmentState.DIAGNOSIS, AssessmentState.REMEDIATION), (
        "remediation must pass through the approval gate"
    )
    for terminal in TERMINAL_STATES:
        assert ALLOWED_TRANSITIONS[terminal] == frozenset()
    for state in set(AssessmentState) - TERMINAL_STATES:
        assert AssessmentState.CANCELLED in ALLOWED_TRANSITIONS[state]


def test_ids_are_prefixed_unique_and_sortable() -> None:
    ids = [new_id(IdPrefix.asm) for _ in range(200)]
    assert len(set(ids)) == 200
    assert all(i.startswith("asm_") and len(i) == 30 for i in ids)


def test_audit_hash_chain_detects_tamper() -> None:
    body = {"id": "aud_x", "action": "scope.approved", "details": {"a": 1}}
    h1 = audit_hash(GENESIS_HASH, body)
    assert h1 == audit_hash(GENESIS_HASH, dict(reversed(list(body.items()))))
    assert h1 != audit_hash(GENESIS_HASH, {**body, "details": {"a": 2}})


def test_generated_artifacts_are_current() -> None:
    stale = [p for p, text in export.render().items() if not p.exists() or p.read_text() != text]
    assert not stale, f"run `uv run python -m shared.export`; stale: {stale}"
    assert examples.main(["--check"]) == 0, "run `uv run python -m shared.examples`"


def test_generated_typescript_compiles(tmp_path: Path) -> None:
    tsc = os.environ.get("TSC") or shutil.which("tsc")
    if not tsc:
        pytest.skip("TypeScript compiler not available; set TSC=/path/to/tsc")
    src = export.GENERATED / "ts" / "contracts.ts"
    probe = tmp_path / "probe.ts"
    fixture = (examples.FIXTURE_DIR / "Finding.json").read_text()
    probe.write_text(
        f'import type {{ Finding, StreamEvent }} from "{src.with_suffix("").as_posix()}";\n'
        f"const f: Finding = {fixture};\n"
        "const kind: Finding['kind'] = f.kind;\n"
        "export const e: Pick<StreamEvent, 'seq'> = { seq: 1 };\n"
        "export { kind };\n"
    )
    result = subprocess.run(
        [
            tsc,
            "--noEmit",
            "--strict",
            "--target",
            "es2022",
            "--moduleResolution",
            "node",
            str(src),
            str(probe),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_readable_producer_ids_accepted_but_prefix_still_enforced() -> None:
    from pydantic import TypeAdapter

    from shared.ids import ExpectationId

    ta = TypeAdapter(ExpectationId)
    assert ta.validate_python("exp_tenant_isolation_payments")
    for bad in ("fnd_tenant_isolation", "exp_short", "exp_has space here", "exp_../../etc"):
        with pytest.raises(ValidationError):
            ta.validate_python(bad)


def test_early_reporting_edges_match_security_agents_runtime() -> None:
    for src in (
        AssessmentState.RECON,
        AssessmentState.VALIDATION,
        AssessmentState.ANALYSIS,
        AssessmentState.DIAGNOSIS,
        AssessmentState.AWAITING_APPROVAL,
        AssessmentState.REMEDIATION,
    ):
        assert can_transition(src, AssessmentState.REPORTING)
    assert not can_transition(AssessmentState.SCOPE_CHECK, AssessmentState.REPORTING)
    assert not can_transition(AssessmentState.FUNCTIONAL_REVIEW, AssessmentState.REPORTING)


def test_check_category_aliases_match_probe_library_ids() -> None:
    from shared.scope import (
        CheckCategory,
        canonical_check_category,
        check_category_allowed,
    )

    assert (
        canonical_check_category("authorization.ownership")
        is CheckCategory.access_control_ownership
    )
    assert canonical_check_category("input.bounds") is CheckCategory.input_validation_bounds
    assert check_category_allowed(
        "access_control.ownership", ["authorization.ownership", "input.bounds"]
    )
    assert check_category_allowed("input_validation.bounds", ["input.bounds"])
    assert not check_category_allowed("access_control.ownership", ["input.bounds"])
    scope = BY_NAME["AuthorizedScope"].model_validate_json(
        (examples.FIXTURE_DIR / "AuthorizedScope.json").read_text()
    )
    assert [c.value for c in scope.allowed_check_categories] == [
        "authorization.ownership",
        "input.bounds",
    ]
    with pytest.raises(ValidationError):
        BY_NAME["AuthorizedScope"].model_validate(
            {**scope.model_dump(mode="json"), "allowed_check_categories": ["made.up.category"]}
        )


def test_live_defense_reviews_cannot_execute_and_health_cannot_be_healthy() -> None:
    from shared.live_defense import StagingEnvironment

    health = BY_NAME["DefenseHealth"].model_validate(
        examples.build()["DefenseHealth"].model_dump(mode="json")
    )
    assert health.status == "unknown"
    with pytest.raises(ValidationError):
        BY_NAME["DefenseHealth"].model_validate(
            {**health.model_dump(mode="json"), "status": "healthy"}
        )
    review = examples.build()["AnalystReview"]
    assert review.executes is False
    with pytest.raises(ValidationError):
        BY_NAME["AnalystReview"].model_validate(
            {**review.model_dump(mode="json"), "executes": True}
        )
    with pytest.raises(ValueError):
        StagingEnvironment("production")
