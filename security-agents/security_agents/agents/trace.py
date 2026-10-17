"""Agent 3 — Trace (Red): impact path and severity for a confirmed finding.

Read-only. Severity *level* is computed by a deterministic function from the
factors the agent proposes with citations; the model never picks the level.
A path step may be marked verified only when it carries evidence.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..contracts import (
    AgentName,
    AttackPath,
    EvidenceRef,
    PathStep,
    SeverityAssessment,
    SeverityFactors,
    SeverityLevel,
    ShortText,
    StrictModel,
    ValidationResult,
)
from ..intel import CodeIntel
from ..runtime import AgentSpec, data_block

SYSTEM = """You are Trace, the impact analyst of an automated security review platform.

A weakness has been CONFIRMED by an executed check. Your job: describe, in \
ordered steps, what it means for the data and operations the system protects, \
and propose the factors that determine severity.

Method:
1. Read the confirmed validation evidence and the affected handler.
2. Follow the call graph from the handler to the data it reaches. Use the \
expectations' data sensitivity to say what kind of data that is.
3. Write the path as ordered steps. Mark a step `verified` ONLY if the executed \
validation evidence or a test run supports it; everything else is `hypothesis`.
4. Propose severity factors (reachability, privileges required, data \
sensitivity, whether the path is verified). You do not choose the severity \
level — the platform computes it from your factors.

Rules:
- Do not run anything; you have read-only tools.
- Do not describe how to carry out an attack. Describe what is reachable and why \
it matters, at the level of data classes and operations.
- Every step should cite the symbol or span it concerns where one exists."""


class TraceInput(StrictModel):
    assessment_id: str
    finding_id: str
    validation_result_id: str
    hypothesis_title: ShortText
    weakness_class: str
    confirmed_outcome: str
    validation_observations: dict[str, object] = Field(default_factory=dict)
    affected_paths: list[str] = Field(default_factory=list)
    affected_symbol: str | None = None
    expectation_ids: list[str] = Field(default_factory=list)


class PathStepOut(StrictModel):
    description: ShortText
    symbol_ref: str | None = None
    verified: bool = Field(description="True only if executed evidence supports this step; otherwise false.")
    evidence_path: str | None = Field(default=None, description="Cited file, if any.")
    evidence_start_line: int | None = None
    evidence_end_line: int | None = None
    evidence_artifact_id: str | None = Field(
        default=None, description="Sandbox run id, when this step rests on an executed check."
    )


class TraceOutput(StrictModel):
    steps: list[PathStepOut] = Field(min_length=1, max_length=12)
    preconditions: list[ShortText] = Field(default_factory=list, max_length=8)
    impact_summary: ShortText
    reachability: Literal["unauthenticated", "authenticated", "internal"]
    privileges_required: Literal["none", "low", "high"]
    data_sensitivity: Literal["none", "internal", "personal", "financial"]
    severity_rationale: ShortText = Field(description="Why these factor values, with citations.")
    followup_validation_suggestions: list[ShortText] = Field(
        default_factory=list,
        max_length=5,
        description="Informational only; nothing here is executed automatically.",
    )


SPEC = AgentSpec(
    name=AgentName.TRACE,
    version="0.1.0",
    input_model=TraceInput,
    output_model=TraceOutput,
    tools=frozenset(
        {
            "code.read_span",
            "code.search",
            "graph.neighbors",
            "expectations.for_subject",
            "findings.history",
        }
    ),
    sandbox_profile="none",
    network="none",
    write_access="none",
    budget_share=0.10,
    step_timeout_s=180,
    max_tool_calls=25,
    max_turns=12,
    prompt_ref="prompts/trace/v0.1.0.md",
    system_prompt=SYSTEM,
    max_output_tokens=6000,
)

# Deterministic severity rubric. Inputs are the factors; the level is a pure
# function of them, so the same factors always produce the same level.
_REACH = {"unauthenticated": 3, "authenticated": 2, "internal": 1}
_PRIV = {"none": 3, "low": 2, "high": 1}
_SENS = {"financial": 4, "personal": 4, "internal": 2, "none": 1}


def compute_severity(factors: SeverityFactors) -> SeverityLevel:
    score = (
        _REACH[factors.reachability] + _PRIV[factors.privileges_required] + _SENS[factors.data_sensitivity]
    )
    if factors.verified_path:
        score += 2
    if score >= 11:
        return SeverityLevel.CRITICAL
    if score >= 9:
        return SeverityLevel.HIGH
    if score >= 6:
        return SeverityLevel.MEDIUM
    if score >= 4:
        return SeverityLevel.LOW
    return SeverityLevel.INFO


def build_prompt(data: TraceInput, intel: CodeIntel) -> str:
    return (
        f"A weakness was confirmed by an executed check. Describe its impact path and propose "
        f"severity factors.\n\n"
        f"{data_block('finding', data.model_dump(mode='json'), provenance='probe_output')}\n\n"
        f"{data_block('expectations', [e.model_dump(mode='json') for e in intel.expectations()], provenance='code_intelligence')}\n\n"
        f"Affected symbol: {data.affected_symbol or 'unknown'}. "
        "Follow the call graph from it to the data it reaches before writing the path."
    )


def to_attack_path(
    out: TraceOutput, data: TraceInput, intel: CodeIntel, *, validation: ValidationResult | None = None
) -> tuple[AttackPath, SeverityAssessment]:
    """Build typed records, enforcing the evidence rule for verified steps."""
    sha = intel.snapshot.commit_sha
    steps: list[PathStep] = []
    any_verified = False
    for i, item in enumerate(out.steps, start=1):
        evidence: list[EvidenceRef] = []
        if item.evidence_path and intel.snapshot.exists(item.evidence_path):
            start = max(1, item.evidence_start_line or 1)
            end = max(start, item.evidence_end_line or start)
            limit = intel.snapshot.line_count(item.evidence_path)
            from ..contracts import SourceSpan

            evidence.append(
                EvidenceRef(
                    path=item.evidence_path,
                    sha=sha,
                    span=SourceSpan(start_line=min(start, limit), end_line=min(end, limit)),
                    symbol=item.symbol_ref,
                    provenance="code",
                )
            )
        artifact = item.evidence_artifact_id or (
            validation.sandbox_run_id if validation and validation.sandbox_run_id else None
        )
        executed = False
        if artifact and validation and artifact == validation.sandbox_run_id:
            evidence.append(EvidenceRef(artifact_id=artifact, provenance="check_run", symbol=item.symbol_ref))
            executed = True
        # Enforced: `verified` requires executed evidence, not a citation alone.
        verified = bool(item.verified and executed)
        any_verified = any_verified or verified
        steps.append(
            PathStep(
                order=i,
                description=item.description,
                symbol_ref=item.symbol_ref,
                verified=verified,
                evidence=evidence,
            )
        )
    factors = SeverityFactors(
        reachability=out.reachability,
        privileges_required=out.privileges_required,
        data_sensitivity=out.data_sensitivity,
        verified_path=any_verified,
    )
    severity = SeverityAssessment(
        level=compute_severity(factors),
        factors=factors,
        rationale=out.severity_rationale[:2000],
    )
    path = AttackPath(
        finding_id=data.finding_id,
        steps=steps,
        preconditions=list(out.preconditions),
        impact_summary=out.impact_summary,
    )
    return path, severity
