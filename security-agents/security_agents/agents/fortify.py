"""Agent 6 — Fortify (Blue): prevention after a verified fix.

Read-only. Promotes the finding's tests into RegressionTest records, proposes
class-level hardening, and drafts future hypotheses for sibling sites (not
executed now). Nothing it returns is applied automatically.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from standards.mapping import check_cwe, d3fend_for_hardening

from ..contracts import (
    AgentName,
    EvidenceRef,
    HardeningRecommendation,
    HypothesisDraft,
    RegressionTest,
    ShortText,
    SourceSpan,
    StrictModel,
)
from ..contracts import export as contract_export
from ..intel import CodeIntel
from ..runtime import AgentSpec, data_block
from ..standards.validators import optional_d3fend_field, validate_d3fend

SYSTEM = """You are Fortify, the hardening agent of an automated security review platform.

A fix has been independently verified. Your job: make this class of problem hard \
to reintroduce.

Produce:
1. Hardening recommendations at the CLASS level — e.g. centralise the check in \
one dependency all routes use, add a policy test covering every route of a \
router, add a lint rule. Each needs a concrete code reference and a note for the \
human reviewer, plus an effort estimate.
2. Future hypothesis drafts for sibling sites that share the pattern. These are \
drafts for a later run; nothing is executed now.
3. Monitoring hints: which entry points should be watched for change.

Rules:
- Recommendations are proposals for humans. You apply nothing and you have \
read-only tools.
- Reference real symbols and spans you looked at.
- Prefer one or two strong structural recommendations over a long weak list."""


class FortifyInput(StrictModel):
    check_category: str = ""
    assessment_id: str
    finding_id: str
    verification_result_id: str
    root_cause_summary: ShortText
    cause_class: str
    cause_paths: list[str] = Field(default_factory=list)
    related_sites: list[ShortText] = Field(default_factory=list)
    tests_added: list[str] = Field(default_factory=list)
    affected_symbol: str | None = None


class RecommendationOut(StrictModel):
    category: Literal["centralize_check", "lint_rule", "policy_test", "config", "monitoring", "other"]
    recommendation: str = Field(max_length=4000)
    reference_path: str | None = None
    reference_start_line: int | None = None
    reference_end_line: int | None = None
    effort: Literal["small", "medium", "large"]
    owner_review_note: ShortText = ""
    d3fend_technique: str | None = Field(
        default=None,
        description="MITRE D3FEND countermeasure id such as D3-AMED, or null when none applies.",
    )

    @field_validator("d3fend_technique")
    @classmethod
    def _known_countermeasure(cls, value: str | None) -> str | None:
        return optional_d3fend_field(value)


class FutureHypothesisOut(StrictModel):
    weakness_class: str = Field(pattern=r"^CWE-\d{1,5}$")

    @field_validator("weakness_class")
    @classmethod
    def _catalog_cwe(cls, value: str) -> str:
        try:
            entry = check_cwe(value)
            if entry.status != "active" or entry.detail.get("kind", "").lower() != "weakness":
                raise ValueError("SCHEMA_INVALID: CWE must be an active weakness")
        except (KeyError, ValueError) as exc:
            raise ValueError(f"SCHEMA_INVALID: rejected CWE identifier {value}: {exc}") from exc
        return value

    title: ShortText
    rationale: ShortText
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class FortifyOutput(StrictModel):
    recommendations: list[RecommendationOut] = Field(min_length=1, max_length=6)
    future_hypotheses: list[FutureHypothesisOut] = Field(default_factory=list, max_length=6)
    monitoring_hints: list[ShortText] = Field(default_factory=list, max_length=8)
    regression_test_names: list[ShortText] = Field(
        default_factory=list,
        max_length=6,
        description="Test ids from the fix that should become permanent regression tests.",
    )


SPEC = AgentSpec(
    name=AgentName.FORTIFY,
    version="0.1.0",
    input_model=FortifyInput,
    output_model=FortifyOutput,
    tools=frozenset(
        {
            "code.read_span",
            "code.search",
            "graph.neighbors",
            "expectations.for_subject",
            "findings.history",
            "static.analyze",
        }
    ),
    sandbox_profile="none",
    network="none",
    write_access="none",
    budget_share=0.10,
    step_timeout_s=180,
    max_tool_calls=20,
    max_turns=10,
    prompt_ref="prompts/fortify/v0.1.0.md",
    system_prompt=SYSTEM,
    max_output_tokens=6000,
)


def build_prompt(data: FortifyInput, intel: CodeIntel) -> str:
    return (
        "A fix for this finding has been independently verified. Propose prevention.\n\n"
        f"{data_block('verified_finding', data.model_dump(mode='json'), provenance='verify_output')}\n\n"
        f"{data_block('expectations', [e.model_dump(mode='json') for e in intel.expectations()], provenance='code_intelligence')}\n\n"
        "Look at the sibling call sites before recommending anything structural."
    )


def to_records(
    out: FortifyOutput, data: FortifyInput, intel: CodeIntel
) -> tuple[list[RegressionTest], list[HardeningRecommendation], list[HypothesisDraft], list[str]]:
    sha = intel.snapshot.commit_sha
    regression: list[RegressionTest] = []
    # Enforced: every verified finding gets >= 1 regression test, built from the
    # tests the patch actually added (not from model text).
    for path in data.tests_added:
        regression.append(
            RegressionTest(
                finding_id=data.finding_id,
                test_path=path,
                test_name=next((n for n in out.regression_test_names if n.startswith(path)), path),
                affected_symbols=[data.affected_symbol] if data.affected_symbol else [],
                origin="patch",
            )
        )
    recommendations: list[HardeningRecommendation] = []
    for item in out.recommendations:
        refs: list[EvidenceRef] = []
        if item.reference_path and intel.snapshot.exists(item.reference_path):
            limit = intel.snapshot.line_count(item.reference_path)
            start = min(max(1, item.reference_start_line or 1), limit)
            end = min(max(start, item.reference_end_line or start), limit)
            refs.append(
                EvidenceRef(
                    path=item.reference_path,
                    sha=sha,
                    span=SourceSpan(start_line=start, end_line=end),
                    provenance="code",
                )
            )
        countermeasure = validate_d3fend(item.d3fend_technique) if item.d3fend_technique else None
        recommendations.append(
            HardeningRecommendation(
                finding_id=data.finding_id,
                category=item.category,
                recommendation=item.recommendation,
                references=refs,
                effort=item.effort,
                d3fend=d3fend_for_hardening(
                    item.category,
                    data.check_category,
                    evidence=[contract_export.evidence_ref(ref, producer="agent:fortify") for ref in refs],
                )[0]
                if refs
                else [],
                owner_review_note=item.owner_review_note,
                d3fend_technique=countermeasure.identifier if countermeasure else None,
                d3fend_label=countermeasure.label if countermeasure else "",
                d3fend_version=countermeasure.version if countermeasure else "",
            )
        )
    drafts: list[HypothesisDraft] = []
    for draft in out.future_hypotheses:
        if not intel.snapshot.exists(draft.path):
            continue
        limit = intel.snapshot.line_count(draft.path)
        start = min(max(1, draft.start_line), limit)
        end = min(max(start, draft.end_line), limit)
        drafts.append(
            HypothesisDraft(
                weakness_class=draft.weakness_class,
                title=draft.title,
                rationale=draft.rationale,
                cited_spans=[
                    EvidenceRef(
                        path=draft.path,
                        sha=sha,
                        span=SourceSpan(start_line=start, end_line=end),
                        provenance="code",
                    )
                ],
            )
        )
    return regression, recommendations, drafts, list(out.monitoring_hints)
