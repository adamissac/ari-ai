"""Agent 2 — Probe (Red): validate or refute ONE hypothesis with executed evidence.

Probe cannot author checks. It may only pick a reviewed template and fill its
typed parameters; the registry scope-checks every run, and the outcome comes
from the template's deterministic `matches_expectation`, not from model text.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator
from standards.mapping import check_cwe

from ..contracts import (
    AgentName,
    EvidenceRef,
    Hypothesis,
    ShortText,
    StrictModel,
    ValidationOutcome,
    ValidationResult,
)
from ..intel import CodeIntel
from ..runtime import AgentSpec, StepRecord, data_block

SYSTEM = """You are Probe, the validation agent of an automated security review platform.

You are given exactly ONE hypothesis about a possible weakness and an authorized \
sandbox target built from the same snapshot. Your job: find out whether the \
hypothesis is real, using only the reviewed check templates available to you.

Method:
1. Call checks.list_templates and pick the template whose category matches the \
hypothesis' suggested check category.
2. Read the hypothesis' cited code and the linked expectation so you fill the \
template's parameters correctly (which route id, which fixture identities).
3. Run it with checks.run_template against the given target id.
4. Read the structured result. The `matches_expectation` field is computed from \
the executed assertions — it is the verdict, not your opinion. If it is false, \
the expectation did not hold and the hypothesis is confirmed. If it is true, the \
expectation held and the hypothesis is refuted. If it is null, the run was \
inconclusive.

Rules:
- You may not invent checks, hosts, URLs or payloads. Parameters must come from \
the target's build recipe as reported by the tools.
- You may run at most a few template runs; make them count.
- Your `interpretation` text explains the result for a human in under 500 \
characters. It cannot change the outcome.
- If no template fits, or the template is not runnable, report inconclusive and \
say exactly what is missing."""


class ProbeInput(StrictModel):
    assessment_id: str
    hypothesis_id: str
    scope_id: str
    target_id: str
    hypothesis_title: ShortText
    weakness_class: str

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

    expected_invariant: str = Field(max_length=4000)
    suggested_check_category: str
    cited_paths: list[str] = Field(default_factory=list)
    expectation_ids: list[str] = Field(default_factory=list)
    subject_routes: list[str] = Field(default_factory=list)


class ProbeOutput(StrictModel):
    outcome: Literal["confirmed", "refuted", "inconclusive"] = Field(
        description="Must agree with matches_expectation from the executed check result."
    )
    check_template_ref: str | None = Field(
        default=None, max_length=120, description="`template_id@version` you ran, if any."
    )
    sandbox_run_id: str | None = Field(
        default=None, max_length=120, description="sandbox_run_id from the check result."
    )
    observations: list[ShortText] = Field(
        default_factory=list,
        max_length=10,
        description="Structured facts from the check result (status codes, counts).",
    )
    interpretation: str = Field(
        default="", max_length=500, description="Human-readable explanation. Non-authoritative."
    )
    missing_capability: ShortText = Field(
        default="", description="If inconclusive: exactly what was unavailable."
    )


SPEC = AgentSpec(
    name=AgentName.PROBE,
    version="0.1.0",
    input_model=ProbeInput,
    output_model=ProbeOutput,
    tools=frozenset(
        {
            "code.read_span",
            "expectations.for_subject",
            "checks.list_templates",
            "checks.run_template",
        }
    ),
    sandbox_profile="check-runner",
    network="target-only",
    write_access="out_dir",
    budget_share=0.20,
    step_timeout_s=180,
    max_tool_calls=12,
    max_turns=10,
    prompt_ref="prompts/probe/v0.1.0.md",
    system_prompt=SYSTEM,
    max_calls_per_tool={"checks.run_template": 3},
    max_output_tokens=4000,
)


def subject_routes(hypothesis: Hypothesis, intel: CodeIntel) -> list[str]:
    found: set[str] = set()
    for entry in intel.entry_points():
        if entry.kind != "http_route" or not entry.method or not entry.path_template:
            continue
        cited = hypothesis.entry_point_id == entry.id or any(
            ref.path == entry.path
            and ref.span is not None
            and ref.span.start_line <= entry.span.end_line
            and entry.span.start_line <= ref.span.end_line
            for ref in hypothesis.cited_spans
        )
        if cited:
            found.add(f"{entry.method.upper()} {entry.path_template}")
    return sorted(found)


def input_from_hypothesis(
    hypothesis: Hypothesis,
    *,
    assessment_id: str,
    scope_id: str,
    target_id: str,
    intel: CodeIntel | None = None,
) -> ProbeInput:
    return ProbeInput(
        assessment_id=assessment_id,
        hypothesis_id=hypothesis.id,
        scope_id=scope_id,
        target_id=target_id,
        hypothesis_title=hypothesis.title,
        weakness_class=hypothesis.weakness_class,
        expected_invariant=hypothesis.rationale[:4000],
        suggested_check_category=hypothesis.suggested_check_category,
        cited_paths=[s.path for s in hypothesis.cited_spans if s.path],
        expectation_ids=list(hypothesis.expectation_ids),
        subject_routes=subject_routes(hypothesis, intel) if intel is not None else [],
    )


def build_prompt(data: ProbeInput, intel: CodeIntel) -> str:
    rows = [
        {
            "path": p,
            "exists_in_snapshot": intel.snapshot.exists(p),
        }
        for p in data.cited_paths
    ]
    return (
        f"Validate or refute this single hypothesis against the authorized target.\n\n"
        f"{data_block('hypothesis', data.model_dump(mode='json'), provenance='scout_output')}\n\n"
        f"{data_block('cited_files', rows, provenance='code_intelligence')}\n\n"
        f"Authorized target id: {data.target_id} (scope {data.scope_id}). "
        f"You may only run checks against this target id.\n"
        + (
            f"Routes handled by the cited code: {', '.join(data.subject_routes)}. Only checks on "
            "these routes decide this hypothesis; a check on any other route does not refute it.\n"
            if data.subject_routes
            else ""
        )
        + (
            "Read the cited code and the linked expectation first, then choose and run the matching "
            "template. Report the outcome that the executed result supports."
        )
    )


def to_validation_result(
    out: ProbeOutput, data: ProbeInput, record: StepRecord, check_runs: list[dict[str, Any]]
) -> ValidationResult:
    """Deterministic reconciliation: the executed result decides the outcome.

    If a check ran, `matches_expectation` sets the outcome and the agent's claim
    is ignored when it disagrees (the disagreement is recorded). With no
    successful run, the outcome is `inconclusive` regardless of what was claimed.
    """
    successful = [r for r in check_runs if not r.get("error")]
    claimed = ValidationOutcome(out.outcome)
    subject = set(data.subject_routes)

    def route_key(run: dict[str, Any]) -> str | None:
        route = run.get("route")
        if not isinstance(route, dict) or not route.get("path_template"):
            return None
        return f"{route.get('method', 'GET')} {route['path_template']}"

    relevant = [r for r in successful if not subject or route_key(r) is None or route_key(r) in subject]
    outside = sorted({k for r in successful if (k := route_key(r)) and subject and k not in subject})
    violating = [r for r in relevant if r.get("matches_expectation") is False]
    holding = [r for r in relevant if r.get("matches_expectation") is True]
    note = ""
    if subject and violating:
        last, outcome = violating[-1], ValidationOutcome.CONFIRMED
    elif subject and holding:
        last, outcome = holding[-1], ValidationOutcome.REFUTED
    elif not subject and violating and holding:
        last, outcome = relevant[-1], ValidationOutcome.INCONCLUSIVE
        note = "checks disagree and the hypothesis subject route is unknown"
    elif relevant:
        last = relevant[-1]
        matches = last.get("matches_expectation")
        outcome = (
            ValidationOutcome.CONFIRMED
            if matches is False
            else ValidationOutcome.REFUTED
            if matches is True
            else ValidationOutcome.INCONCLUSIVE
        )
    else:
        last, outcome = None, ValidationOutcome.INCONCLUSIVE
        if outside:
            note = f"checks ran only on routes outside the hypothesis subject: {', '.join(outside)}"

    observations: dict[str, Any] = {
        "agent_claimed_outcome": claimed.value,
        "outcome_source": "executed_check" if last else "no_successful_check_run",
        "agent_notes": out.observations[:10],
    }
    if note:
        observations["reconciliation"] = note
    if outside:
        observations["routes_outside_subject"] = outside
    if subject:
        observations["subject_routes"] = sorted(subject)
    if claimed != outcome:
        observations["disagreement"] = (
            f"agent claimed {claimed.value}; executed evidence gives {outcome.value}"
        )
    if last:
        for key in (
            "passed",
            "failed",
            "errors",
            "failing_tests",
            "exit_code",
            "driver",
            "isolation_level",
            "network",
            "params_hash",
            "transport",
            "target_contacted",
            "target_requests",
            "target_log_sha256",
        ):
            if key in last:
                observations[key] = last[key]
    elif out.missing_capability:
        observations["missing_capability"] = out.missing_capability

    evidence: list[EvidenceRef] = []
    if last:
        evidence.append(
            EvidenceRef(
                artifact_id=str(last.get("sandbox_run_id")),
                provenance="check_run",
                symbol=str(last.get("template_ref")),
            )
        )
    return ValidationResult(
        hypothesis_id=data.hypothesis_id,
        outcome=outcome,
        check_template_id=(last or {}).get("template_id"),
        check_template_version=(last or {}).get("template_version"),
        parameters=dict((last or {}).get("parameters") or {}),
        sandbox_run_id=(last or {}).get("sandbox_run_id"),
        observations=observations,
        evidence=evidence,
        interpretation=out.interpretation[:500],
    )
