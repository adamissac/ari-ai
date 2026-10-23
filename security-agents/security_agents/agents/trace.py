from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator
from shared.standards import CVSSAssessment, CVSSMetricValue
from standards import cvss31 as cvss
from standards.cvss import vector as cvss4_vector

from ..contracts import (
    AgentName,
    AttackPath,
    CvssMetricEvidence,
    EvidenceRef,
    PathStep,
    SeverityAssessment,
    SeverityFactors,
    SeverityLevel,
    ShortText,
    SourceSpan,
    StrictModel,
    ValidationResult,
)
from ..contracts import export as contract_export
from ..intel import CodeIntel
from ..runtime import AgentSpec, data_block
from ..standards.fields import attack_entry, optional_attack_field

SYSTEM = """You are Trace, the impact analyst of an automated security review platform.

A weakness has been CONFIRMED by an executed check. Your job: describe, in \
ordered steps, what it means for the data and operations the system protects, \
and propose the eight CVSS v3.1 base metrics with the evidence for each.

Method:
1. Read the confirmed validation evidence and the affected handler.
2. Follow the call graph from the handler to the data it reaches. Use the \
expectations' data sensitivity to say what kind of data that is.
3. Write the path as ordered steps. Mark a step `verified` ONLY if the executed \
validation evidence or a test run supports it; everything else is reasoning.
4. For each step you may name one MITRE ATT&CK Enterprise technique id when one \
genuinely describes it. Leave it null when no technique applies; web \
authorization defects often have no applicable technique, and that is an \
acceptable answer.
5. Propose all eight CVSS v3.1 base metrics: AV, AC, PR, UI, S, C, I, A. For \
each, cite the file span or the executed check run that supports the value. A \
metric without a citation is recorded as unverified.

Rules:
- You never choose a score, a rating or a severity level. The platform computes \
the CVSS vector, base score and rating from your metrics, and that base score \
measures severity, not business risk.
- You may also propose all eleven CVSS v4.0 base metrics in `cvss_metrics`, each \
backed by the executed validation run in `cvss_metric_artifacts`. Omit them if \
any v4.0 metric is uncertain. They are recorded as provisional assumptions that \
need human review and never set the platform severity level.
- Do not run anything; you have read-only tools.
- Do not describe how to carry out an attack. Describe what is reachable and why \
it matters, at the level of data classes and operations."""

MetricName = Literal["AV", "AC", "PR", "UI", "S", "C", "I", "A"]


class TraceInput(StrictModel):
    check_category: str = ""
    assessment_id: str
    finding_id: str
    validation_result_id: str
    sandbox_run_id: str | None = None
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
    attack_technique: str | None = Field(
        default=None,
        description="MITRE ATT&CK Enterprise technique id such as T1190, or null when no technique applies.",
    )

    @field_validator("attack_technique")
    @classmethod
    def _known_technique(cls, value: str | None) -> str | None:
        return optional_attack_field(value)


class CvssMetricProposal(StrictModel):
    metric: MetricName
    value: str = Field(max_length=1, description="Single-letter CVSS v3.1 value for this metric.")
    rationale: ShortText = Field(description="Why this value, in one or two sentences.")
    evidence_path: str | None = Field(default=None, description="File span supporting the value.")
    evidence_start_line: int | None = None
    evidence_end_line: int | None = None
    evidence_artifact_id: str | None = Field(
        default=None, description="Executed check run supporting the value, if any."
    )

    @model_validator(mode="after")
    def _allowed_value(self) -> CvssMetricProposal:
        allowed = cvss.ALLOWED[self.metric]
        if self.value not in allowed:
            raise ValueError(f"{self.metric} must be one of {', '.join(allowed)}; got {self.value!r}")
        return self


class TraceOutput(StrictModel):
    cvss_metrics: dict[str, str] | None = Field(
        default=None,
        description="Optional complete CVSS v4.0 base metrics, each backed by an executed evidence artifact. Never supply a score.",
    )
    cvss_metric_artifacts: dict[str, str] = Field(default_factory=dict)
    steps: list[PathStepOut] = Field(min_length=1, max_length=12)
    preconditions: list[ShortText] = Field(default_factory=list, max_length=8)
    impact_summary: ShortText
    cvss_base_metrics: list[CvssMetricProposal] = Field(
        min_length=8, max_length=8, description="Exactly one proposal for each of AV, AC, PR, UI, S, C, I, A."
    )
    severity_rationale: ShortText = Field(description="Why these metric values, with citations.")
    followup_validation_suggestions: list[ShortText] = Field(
        default_factory=list,
        max_length=5,
        description="Informational only; nothing here is executed automatically.",
    )

    @model_validator(mode="after")
    def _complete_cvss4(self) -> TraceOutput:
        if self.cvss_metrics is not None:
            cvss4_vector(self.cvss_metrics)
            if set(self.cvss_metrics) != set(self.cvss_metric_artifacts):
                raise ValueError("Every explicit CVSS v4.0 metric needs its supporting artifact")
        return self

    @model_validator(mode="after")
    def _each_metric_once(self) -> TraceOutput:
        names = [proposal.metric for proposal in self.cvss_base_metrics]
        missing = [name for name in cvss.BASE_ORDER if name not in names]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if missing or duplicated:
            raise ValueError(
                f"cvss_base_metrics needs each of {', '.join(cvss.BASE_ORDER)} exactly once; "
                f"missing {missing or 'none'}, repeated {duplicated or 'none'}"
            )
        return self


SPEC = AgentSpec(
    name=AgentName.TRACE,
    version="0.3.0",
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
    prompt_ref="prompts/trace/v0.3.0.md",
    system_prompt=SYSTEM,
    max_output_tokens=16000,  # thinking counts toward this; 4-8k ran out on real repos
)

SENSITIVITY_ORDER = ("none", "internal", "personal", "financial")


def build_prompt(data: TraceInput, intel: CodeIntel) -> str:
    return (
        "A weakness was confirmed by an executed check. Describe its impact path and propose "
        "the eight CVSS v3.1 base metrics with evidence.\n\n"
        f"{data_block('finding', data.model_dump(mode='json'), provenance='probe_output')}\n\n"
        f"{data_block('expectations', [e.model_dump(mode='json') for e in intel.expectations()], provenance='code_intelligence')}\n\n"
        f"Affected symbol: {data.affected_symbol or 'unknown'}. "
        "Follow the call graph from it to the data it reaches before writing the path."
    )


def _span_evidence(
    intel: CodeIntel, path: str | None, start: int | None, end: int | None, symbol: str | None
) -> EvidenceRef | None:
    if not path or not intel.snapshot.exists(path):
        return None
    limit = intel.snapshot.line_count(path)
    first = min(max(1, start or 1), limit)
    last = min(max(first, end or first), limit)
    return EvidenceRef(
        path=path,
        sha=intel.snapshot.commit_sha,
        span=SourceSpan(start_line=first, end_line=last),
        symbol=symbol,
        provenance="code",
    )


def _data_sensitivity(data: TraceInput, intel: CodeIntel) -> str:
    linked = [e for e in intel.expectations() if e.id in set(data.expectation_ids)]
    values = [e.data_sensitivity for e in linked if e.data_sensitivity in SENSITIVITY_ORDER]
    if not values:
        return "none"
    return max(values, key=SENSITIVITY_ORDER.index)


def _factors(metrics: cvss.BaseMetrics, sensitivity: str, verified: bool) -> SeverityFactors:
    if metrics.AV in ("L", "P"):
        reachability = "internal"
    elif metrics.PR == "N":
        reachability = "unauthenticated"
    else:
        reachability = "authenticated"
    return SeverityFactors(
        reachability=reachability,
        privileges_required={"N": "none", "L": "low", "H": "high"}[metrics.PR],
        data_sensitivity=sensitivity,
        verified_path=verified,
    )


def to_attack_path(
    out: TraceOutput, data: TraceInput, intel: CodeIntel, *, validation: ValidationResult | None = None
) -> tuple[AttackPath, SeverityAssessment]:
    executed_run = validation.sandbox_run_id if validation and validation.sandbox_run_id else None
    by_metric = {proposal.metric: proposal for proposal in out.cvss_base_metrics}
    metrics = cvss.BaseMetrics(**{name: by_metric[name].value for name in cvss.BASE_ORDER})
    metrics_reachability = _factors(metrics, "none", False).reachability
    steps: list[PathStep] = []
    any_verified = False
    for index, item in enumerate(out.steps, start=1):
        evidence: list[EvidenceRef] = []
        span = _span_evidence(
            intel, item.evidence_path, item.evidence_start_line, item.evidence_end_line, item.symbol_ref
        )
        if span is not None:
            evidence.append(span)
        artifact = item.evidence_artifact_id or executed_run
        executed = bool(artifact and executed_run and artifact == executed_run)
        if executed:
            evidence.append(EvidenceRef(artifact_id=artifact, provenance="check_run", symbol=item.symbol_ref))
        verified = bool(item.verified and executed)
        any_verified = any_verified or verified
        reviewed_attack = _reviewed_attack(data, metrics_reachability, evidence) if verified else []
        technique = attack_entry(item.attack_technique) if item.attack_technique else None
        steps.append(
            PathStep(
                order=index,
                description=item.description,
                symbol_ref=item.symbol_ref,
                verified=verified,
                evidence=evidence,
                attack=reviewed_attack,
                attack_technique=technique.id if technique else None,
                attack_technique_name=technique.name if technique else "",
                attack_version=technique.catalog_version if technique else "",
                attack_label=(
                    "Enterprise ATT&CK technique (model proposal, validated against the pinned index)"
                    if technique
                    else "no applicable technique"
                ),
            )
        )

    result = cvss.base_score(metrics)
    metric_evidence: list[CvssMetricEvidence] = []
    for name in cvss.BASE_ORDER:
        proposal = by_metric[name]
        cited: list[EvidenceRef] = []
        span = _span_evidence(
            intel, proposal.evidence_path, proposal.evidence_start_line, proposal.evidence_end_line, None
        )
        if span is not None:
            cited.append(span)
        if proposal.evidence_artifact_id and executed_run and proposal.evidence_artifact_id == executed_run:
            cited.append(EvidenceRef(artifact_id=executed_run, provenance="check_run"))
        metric_evidence.append(
            CvssMetricEvidence(
                metric=name,
                value=proposal.value,
                status="cited" if cited else "unverified",
                evidence=cited,
                rationale=proposal.rationale[:2000],
            )
        )

    severity = SeverityAssessment(
        level=SeverityLevel(cvss.severity_level(result)),
        factors=_factors(metrics, _data_sensitivity(data, intel), any_verified),
        rationale=out.severity_rationale[:2000],
        cvss_version="3.1",
        cvss_vector=result.vector,
        cvss_base_score=result.score,
        cvss_rating=result.rating,
        score_kind=cvss.SCORE_KIND,
        level_source="derived from the CVSS v3.1 qualitative rating computed by the platform",
        metric_evidence=metric_evidence,
        cvss=_cvss4(out, validation),
    )
    path = AttackPath(
        finding_id=data.finding_id,
        steps=steps,
        preconditions=list(out.preconditions),
        impact_summary=out.impact_summary,
    )
    return path, severity


def _cvss4(out: TraceOutput, validation: ValidationResult | None) -> CVSSAssessment | None:
    if out.cvss_metrics is None or validation is None or not validation.sandbox_run_id:
        return None
    if any(artifact != validation.sandbox_run_id for artifact in out.cvss_metric_artifacts.values()):
        return None
    evidence = [contract_export.evidence_ref(ref, producer="agent:trace") for ref in validation.evidence]
    if not evidence:
        return None
    from standards.cvss_assess import assess

    from ..contracts import utcnow

    return assess(
        {},
        now=utcnow(),
        overrides={
            metric: CVSSMetricValue(
                metric=metric,
                value=value,
                basis="assumption",
                rationale=(
                    "Model-proposed metric; the cited run supplies context, not proof of this metric. "
                    "Human review required. " + out.severity_rationale
                )[:500],
                evidence=evidence,
            )
            for metric, value in out.cvss_metrics.items()
        },
        assessor="agent:trace:provisional-metric-assumptions",
    )


def _reviewed_attack(data: TraceInput, reachability: str, evidence: list[EvidenceRef]) -> list:
    from shared.standards import Observation
    from standards.mapping import attack_for_check

    return attack_for_check(
        data.check_category,
        {"reachability": reachability},
        observation=Observation.observed_in_sandbox,
        evidence=[contract_export.evidence_ref(ref, producer="agent:trace") for ref in evidence],
    )[0]
