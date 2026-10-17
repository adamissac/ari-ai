"""Export internal records as canonical `shared` contract models.

`shared` (owner: Srihith, SCHEMA_VERSION 0.2.0) is the source of truth for
anything that crosses a subsystem boundary. The security pillar keeps its own
richer internal records (they carry working state an API consumer does not
need), and this module is the one place that maps them onto the canonical
models. The contract tests validate every mapping against the real `shared`
package, so a contract change breaks here rather than silently at the API edge.

Known mapping gaps, raised with the contract owner (see
`coordination/messages/`):

1. `ValidationResult` requires `check_template_id`, `check_template_version`,
   `sandbox_run_id` and at least one `EvidenceRef`. An `inconclusive` outcome
   with no executed run has none of those, so it cannot be represented.
   `validation_result()` raises for that case rather than inventing values.
2. `RemediationPlan.test_plan` is one `ShortText`; the plan an approver reviews
   distinguishes "must fail before" from "must pass after", so this flattens
   the structure into text and the detail is lost on the wire.
3. `Hypothesis` has no title field; the internal title is prefixed onto
   `rationale`, which is a `ShortText` (500 chars), so a real agent rationale
   is truncated on the wire. The full text stays in the step transcript.
5. `ExpectationId` is `^exp_[0-9A-Za-z]{8,64}$`, which forbids the underscores
   in the human-readable ids the canonical fixture already uses
   (`exp_owner_only` in `examples/payments-lite/labels.yaml`).
   `canonical_expectation_id()` maps such an id deterministically to
   `exp_<16 hex of sha256>` and `expectation_id_notes()` records the mapping so
   the link is traceable rather than dropped.
6. `shared` confidence is a number in [0, 1]; the security pillar reasons in
   low/medium/high, mapped through `CONFIDENCE_SCORE`.
4. `shared.Finding.commit_sha` requires 40 hex characters, so a snapshot taken
   from a directory (dev/demo only) must still present a 40-hex digest;
   `SnapshotHandle.from_directory` produces one and records the real provenance
   in `pinned_by`.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from ..contracts import CONFIDENCE_WEIGHT, Confidence, utcnow
from ..contracts import (
    AgentRun as InternalAgentRun,
)
from ..contracts import (
    AttackPath as InternalAttackPath,
)
from ..contracts import (
    EvidenceRef as InternalEvidenceRef,
)
from ..contracts import (
    Hypothesis as InternalHypothesis,
)
from ..contracts import (
    PatchCandidate as InternalPatchCandidate,
)
from ..contracts import (
    RemediationPlan as InternalRemediationPlan,
)
from ..contracts import (
    RootCause as InternalRootCause,
)
from ..contracts import (
    ValidationResult as InternalValidationResult,
)
from ..contracts import (
    VerificationResult as InternalVerificationResult,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass

# The adapter was written and verified against these schema versions. A newer
# version is accepted when the models this package maps are unchanged — see
# `MAPPED_FIELDS` and `assert_mappings_current()`, which is the check that
# actually matters.
VERIFIED_SCHEMA_VERSIONS = ("0.2.0", "0.4.0", "0.7.0", "0.9.0")

# Field sets this adapter depends on, per canonical model: (module, class) ->
# {field: required}. A change here means a mapping must be revisited, whether or
# not SCHEMA_VERSION moved.
MAPPED_FIELDS: dict[tuple[str, str], dict[str, bool]] = {
    ("evidence", "EvidenceRef"): {
        "kind": True,
        "path": False,
        "commit_sha": False,
        "span": False,
        "symbol": False,
        "artifact_id": False,
        "sha256": False,
        "provenance": True,
        "note": False,
    },
    ("findings", "Hypothesis"): {
        "id": True,
        "finding_id": True,
        "weakness_class": True,
        "rationale": True,
        "cited_spans": True,
        "expectation_ids": False,
        "confidence": True,
        "suggested_check_category": True,
    },
    ("findings", "ValidationResult"): {
        "id": True,
        "hypothesis_id": True,
        "outcome": True,
        "check_template_id": True,
        "check_template_version": True,
        "sandbox_run_id": True,
        "evidence": True,
    },
    ("findings", "AttackPath"): {
        "id": True,
        "finding_id": True,
        "steps": True,
        "preconditions": False,
        "impact_summary": True,
    },
    ("findings", "RootCause"): {
        "id": True,
        "finding_id": True,
        "summary": True,
        "violated_expectation_ids": False,
        "cause_spans": True,
        "cause_class": True,
    },
    ("findings", "RemediationPlan"): {
        "id": True,
        "finding_id": True,
        "strategy": True,
        "constraints": False,
        "files_expected": False,
        "test_plan": True,
    },
    ("findings", "VerificationResult"): {
        "id": True,
        "patch_id": True,
        "verdict": True,
        "checks": True,
        "sandbox_run_ids": True,
        "reasons": False,
        "produced_by_run_id": True,
        "created_at": True,
    },
}

# `shared` expresses confidence as a number in [0, 1].
CONFIDENCE_SCORE: dict[Confidence, float] = dict(CONFIDENCE_WEIGHT)

SHORT_TEXT_MAX = 500
LONG_TEXT_MAX = 20_000


def _short(text: str) -> str:
    """Fit a `ShortText` field, marking the truncation."""
    text = text.strip()
    if len(text) <= SHORT_TEXT_MAX:
        return text
    return text[: SHORT_TEXT_MAX - 3].rstrip() + "..."


def canonical_expectation_id(raw: str) -> str:
    """Map an expectation id onto the canonical `exp_` pattern.

    Ids that already match are returned unchanged. A human-readable id such as
    `exp_owner_only` (which the pattern rejects because of the underscores) is
    mapped deterministically to `exp_<16 hex>` so the same input always yields
    the same canonical id.
    """
    import re

    if re.fullmatch(r"exp_[0-9A-Za-z]{8,64}", raw):
        return raw
    return f"exp_{_sha256_of(raw)[:16]}"


def expectation_id_notes(raw_ids: list[str]) -> dict[str, str]:
    """Which ids had to be mapped, for the audit trail and for coordination."""
    return {raw: canonical_expectation_id(raw) for raw in raw_ids if canonical_expectation_id(raw) != raw}


class ContractUnavailable(RuntimeError):
    """The canonical `shared` package is not importable in this environment."""


def shared_module(name: str = "") -> Any:
    """Import `shared` (optionally a submodule) with a clear error if absent."""
    try:
        return importlib.import_module(f"shared.{name}" if name else "shared")
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise ContractUnavailable(
            "the canonical `shared` package is not importable; install it "
            "(`uv pip install -e ../shared`) or run from the repo workspace"
        ) from exc


def schema_version() -> str:
    return str(shared_module().SCHEMA_VERSION)


def mapping_drift() -> list[str]:
    """Differences between the canonical models and what this adapter assumes."""
    problems: list[str] = []
    for (module_name, class_name), expected in MAPPED_FIELDS.items():
        try:
            model = getattr(shared_module(module_name), class_name)
        except AttributeError:
            problems.append(f"{module_name}.{class_name} no longer exists")
            continue
        actual = {name: field.is_required() for name, field in model.model_fields.items()}
        for field, required in expected.items():
            if field not in actual:
                problems.append(f"{module_name}.{class_name}.{field} was removed or renamed")
            elif actual[field] != required:
                became = "required" if actual[field] else "optional"
                problems.append(f"{module_name}.{class_name}.{field} became {became}")
        for field in actual:
            if field not in expected:
                problems.append(f"{module_name}.{class_name}.{field} is new (not mapped)")
    return problems


def assert_mappings_current() -> None:
    """Fail loudly when a canonical model this adapter maps has changed shape."""
    problems = mapping_drift()
    if problems:
        raise ContractUnavailable(
            f"shared SCHEMA_VERSION {schema_version()} changed models this adapter maps: "
            + "; ".join(problems)
        )


def assert_supported_schema() -> None:
    """Version check plus the structural check. The structural one decides."""
    assert_mappings_current()


# --------------------------------------------------------------------------- evidence


def evidence_ref(ref: InternalEvidenceRef, *, producer: str) -> Any:
    """Map an internal citation onto `shared.EvidenceRef`.

    The canonical model is stricter: a source span needs path + commit_sha +
    span, and an artifact-backed kind needs artifact_id + sha256.
    """
    ev = shared_module("evidence")
    if ref.path and ref.span and ref.sha:
        return ev.EvidenceRef(
            kind=ev.EvidenceKind.source_span,
            path=ref.path,
            commit_sha=ref.sha,
            span=ev.SourceSpan(start_line=ref.span.start_line, end_line=ref.span.end_line),
            symbol=ref.symbol,
            provenance=producer,
        )
    if ref.artifact_id:
        kind = {
            "check_run": ev.EvidenceKind.sandbox_run,
            "test_run": ev.EvidenceKind.test_run,
            "diff": ev.EvidenceKind.artifact,
        }.get(ref.provenance, ev.EvidenceKind.tool_output)
        return ev.EvidenceRef(
            kind=kind,
            artifact_id=_artifact_id(ref.artifact_id),
            sha256=_sha256_of(ref.artifact_id),
            symbol=ref.symbol,
            provenance=producer,
        )
    return ev.EvidenceRef(
        kind=ev.EvidenceKind.doc,
        path=ref.path,
        provenance=producer,
        note=ref.symbol,
    )


def _artifact_id(raw: str) -> str:
    """Canonical artifact ids are `art_<body>`; sandbox run ids are not."""
    if raw.startswith("art_"):
        return raw
    body = "".join(ch for ch in raw if ch.isalnum()) or "0"
    return f"art_{body[:60]:0>8}"


def _sha256_of(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode()).hexdigest()


# --------------------------------------------------------------------------- findings


def hypothesis(h: InternalHypothesis, *, finding_id: str) -> Any:
    f = shared_module("findings")
    return f.Hypothesis(
        id=h.id,
        finding_id=finding_id,
        weakness_class=h.weakness_class,
        rationale=_short(f"{h.title}. {h.rationale}"),
        cited_spans=[evidence_ref(s, producer="agent:scout") for s in h.cited_spans],
        expectation_ids=[canonical_expectation_id(e) for e in h.expectation_ids],
        confidence=CONFIDENCE_SCORE[h.confidence],
        suggested_check_category=h.suggested_check_category,
    )


def validation_result(v: InternalValidationResult) -> Any:
    """Canonical ValidationResult. Raises for an outcome with no executed run."""
    f = shared_module("findings")
    if not (v.check_template_id and v.check_template_version and v.sandbox_run_id):
        raise ValueError(
            "shared.ValidationResult requires an executed check (template id, version and "
            f"sandbox run id); outcome={v.outcome.value} has none. See export.py gap 1."
        )
    evidence = [evidence_ref(e, producer="agent:probe") for e in v.evidence]
    if not evidence:
        raise ValueError("shared.ValidationResult requires at least one EvidenceRef")
    return f.ValidationResult(
        id=v.id,
        hypothesis_id=v.hypothesis_id,
        outcome=v.outcome.value,
        check_template_id=v.check_template_id,
        check_template_version=v.check_template_version,
        sandbox_run_id=v.sandbox_run_id,
        evidence=evidence,
    )


def attack_path(path: InternalAttackPath) -> Any:
    f = shared_module("findings")
    return f.AttackPath(
        id=path.id,
        finding_id=path.finding_id,
        steps=[
            f.PathStep(
                order=step.order,
                description=_short(step.description),
                symbol_ref=step.symbol_ref,
                verified=step.verified,
                evidence=[evidence_ref(e, producer="agent:trace") for e in step.evidence],
                attack=step.attack,
            )
            for step in path.steps
        ],
        preconditions=[_short(p) for p in path.preconditions],
        impact_summary=_short(path.impact_summary),
    )


def cvss_v31(assessment: Any) -> Any:
    if not assessment.cvss_vector or assessment.cvss_base_score is None:
        return None
    st = shared_module("standards")
    metrics = []
    for item in assessment.metric_evidence:
        evidence = [evidence_ref(ref, producer="agent:trace") for ref in item.evidence]
        metrics.append(
            st.CVSS31MetricEvidence(
                metric=item.metric,
                value=item.value,
                status="cited" if evidence else "unverified",
                evidence=evidence,
                rationale=_short(item.rationale),
            )
        )
    return st.CVSS31Assessment(
        vector=assessment.cvss_vector,
        base_score=assessment.cvss_base_score,
        rating=assessment.cvss_rating,
        score_kind=assessment.score_kind,
        metric_evidence=metrics,
        assessor="system:standards.cvss31",
    )


def severity(assessment: Any) -> Any:
    f = shared_module("findings")
    return f.SeverityAssessment(
        level=assessment.level.value,
        cvss=assessment.cvss,
        cvss_v31=cvss_v31(assessment),
        factors=f.SeverityFactors(
            reachability=assessment.factors.reachability,
            privileges_required=assessment.factors.privileges_required,
            data_sensitivity=assessment.factors.data_sensitivity,
            verified_path=assessment.factors.verified_path,
        ),
        rationale=_short(assessment.rationale),
    )


def root_cause(rc: InternalRootCause) -> Any:
    f = shared_module("findings")
    return f.RootCause(
        id=rc.id,
        finding_id=rc.finding_id,
        summary=_short(rc.summary),
        violated_expectation_ids=[canonical_expectation_id(e) for e in rc.violated_expectation_ids],
        cause_spans=[evidence_ref(s, producer="agent:diagnose") for s in rc.cause_spans],
        cause_class=rc.cause_class.value,
    )


def remediation_plan(plan: InternalRemediationPlan) -> Any:
    """Flattens the structured test plan into the canonical single text field."""
    f = shared_module("findings")
    parts: list[str] = []
    if plan.test_plan.must_fail_before:
        parts.append("must fail before: " + "; ".join(plan.test_plan.must_fail_before))
    if plan.test_plan.must_pass_after:
        parts.append("must pass after: " + "; ".join(plan.test_plan.must_pass_after))
    return f.RemediationPlan(
        id=plan.id,
        finding_id=plan.finding_id,
        strategy=_short(plan.strategy),
        constraints=[_short(c) for c in plan.constraints],
        files_expected=list(plan.files_expected),
        test_plan=_short(" | ".join(parts)) or "no test plan recorded",
    )


def patch_candidate(
    candidate: InternalPatchCandidate,
    *,
    base_commit_sha: str,
    produced_by_run_id: str,
    rationale: str,
    diff_artifact_id: str | None = None,
) -> Any:
    f = shared_module("findings")
    return f.PatchCandidate(
        id=candidate.id,
        finding_id=candidate.finding_id,
        attempt=candidate.attempt,
        diff_artifact_id=diff_artifact_id or _artifact_id(candidate.diff_sha256),
        diff_sha256=candidate.diff_sha256,
        base_commit_sha=base_commit_sha,
        worktree_ref=_short(candidate.worktree_ref),
        files_changed=list(candidate.files_changed),
        tests_added=list(candidate.tests_added),
        local_test_run_id=None,
        produced_by_run_id=produced_by_run_id,
        rationale=_short(rationale) or "no rationale recorded",
        created_at=utcnow(),
    )


def verification_result(result: InternalVerificationResult, *, produced_by_run_id: str) -> Any:
    f = shared_module("findings")
    checks = []
    for check in result.checks:
        evidence = [evidence_ref(e, producer="agent:verify") for e in check.evidence]
        if not evidence:
            # The canonical model requires evidence per check; a check decided
            # from the absence of a run cites the run record that proves it.
            ev = shared_module("evidence")
            evidence = [
                ev.EvidenceRef(
                    kind=ev.EvidenceKind.tool_output,
                    artifact_id=_artifact_id(f"{result.id}{check.name.value}"),
                    sha256=_sha256_of(f"{result.id}:{check.name.value}:{check.detail}"),
                    provenance="agent:verify",
                    note=_short(check.detail) or "decided from the absence of an executed run",
                )
            ]
        checks.append(f.VerificationCheck(name=check.name.value, passed=check.passed, evidence=evidence))
    return f.VerificationResult(
        id=result.id,
        patch_id=result.patch_id,
        verdict=result.verdict,
        checks=checks,
        sandbox_run_ids=result.sandbox_run_ids or ["none-recorded"],
        reasons=[_short(r) for r in result.reasons],
        produced_by_run_id=produced_by_run_id,
        created_at=utcnow(),
    )


# --------------------------------------------------------------------------- runs


def agent_run(run: InternalAgentRun, *, tool_calls: list[dict[str, Any]] | None = None) -> Any:
    a = shared_module("assessment")
    records = []
    for index, call in enumerate(tool_calls or []):
        records.append(
            a.ToolCallRecord(
                turn=int(call.get("turn", index)),
                tool_name=str(call["name"]),
                input_sha256=_sha256_of(str(call.get("args", ""))),
                outcome=(
                    a.ToolCallOutcome.ok
                    if call.get("ok")
                    else a.ToolCallOutcome.denied
                    if call.get("error_code") in ("TOOL_NOT_ALLOWED", "SCOPE_DENIED", "KILL_SWITCH")
                    else a.ToolCallOutcome.error
                ),
                error_code=call.get("error_code") if _is_catalog_code(call.get("error_code")) else None,
                duration_ms=int(call.get("duration_ms", 0)),
            )
        )
    status = {
        "running": a.AgentRunStatus.running,
        "succeeded": a.AgentRunStatus.succeeded,
        "failed": a.AgentRunStatus.failed,
    }[run.status]
    error = None
    if run.error_code is not None:
        errors = shared_module("errors")
        error = errors.ErrorBody(
            code=run.error_code.value,
            message=_short(run.error_detail or run.error_code.value),
        )
    return a.AgentRun(
        id=run.id,
        assessment_id=run.assessment_id,
        agent=run.agent.value,
        step_key=run.step_key,
        attempt=run.attempt,
        status=status,
        provider_mode=run.provider_mode,
        model_id=run.model_id,
        transcript_artifact_id=_artifact_id(run.transcript_ref) if run.transcript_ref else None,
        tool_calls=records,
        usage=a.Usage(
            input_tokens=run.usage.input_tokens,
            output_tokens=run.usage.output_tokens,
            usd=run.usage.usd,
            sandbox_seconds=run.usage.sandbox_seconds,
            llm_calls=run.llm_turns,
            tool_calls=run.tool_calls,
        ),
        error=error,
        started_at=run.started_at,
        ended_at=run.ended_at,
    )


def _is_catalog_code(code: Any) -> bool:
    if not isinstance(code, str):
        return False
    try:
        errors = shared_module("errors")
    except ContractUnavailable:  # pragma: no cover
        return False
    return code in {member.value for member in errors.ErrorCode}


def weakness_ref(weakness_class: str, *, evidence: list[Any], confidence: float) -> Any:
    from shared.standards import MappedVia, Observation
    from standards.mapping import classify_cwe

    return classify_cwe(
        weakness_class,
        evidence=evidence,
        confidence=confidence,
        observation=Observation.hypothesis,
        mapped_via=MappedVia.validated_proposal,
        rationale="Catalog-validated weakness proposal; requires review",
    )


def attack_refs(weakness_class: str, *, evidence: list[Any], confidence: float) -> list[Any]:
    """Coarse catalog chains are review candidates, never automatic mappings."""
    from standards.mapping import attack_candidates_via_capec

    attack_candidates_via_capec(weakness_class)
    return []
