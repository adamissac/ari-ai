"""Agent 4 — Diagnose (Blue): root cause and a reviewable remediation plan.

Read-only. The plan goes to a human approval gate; Diagnose cannot approve it
and its output schema contains no field that could.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..contracts import (
    AgentName,
    CauseClass,
    EvidenceRef,
    RemediationPlan,
    RemediationTestPlan,
    RootCause,
    ShortText,
    SourceSpan,
    StrictModel,
)
from ..intel import CodeIntel
from ..runtime import AgentSpec, data_block

SYSTEM = """You are Diagnose, the root-cause analyst of an automated security review platform.

A weakness has been confirmed and its impact traced. Your job: find WHERE the \
intended behaviour is actually violated — not where the symptom shows — and write \
a remediation plan a human reviewer can approve.

Method:
1. Read the confirmed evidence and the affected handler.
2. Follow the call graph to the function that should enforce the guarantee. \
Prefer the shared data-access or dependency function over a single route when \
several routes depend on it; name the other call sites you find.
3. Classify the cause: missing_check, wrong_check, unsafe_default, logic_error, \
dependency, or configuration.
4. Write the plan: strategy, constraints that must hold (which confirmed \
expectations must keep passing), the exact files you expect to change, and a \
test plan saying which tests must FAIL before the fix and PASS after it.

Rules:
- `files_expected` must be real paths in the snapshot (new test files may be \
listed too). Keep the list minimal — this is the boundary a later patch is held to.
- Cause spans must be spans you read.
- You do not write the patch and you do not approve anything."""


class DiagnoseInput(StrictModel):
    assessment_id: str
    finding_id: str
    weakness_class: str
    hypothesis_title: ShortText
    severity_level: str
    impact_summary: ShortText
    validation_observations: dict[str, object] = Field(default_factory=dict)
    affected_symbol: str | None = None
    affected_paths: list[str] = Field(default_factory=list)
    violated_expectation_ids: list[str] = Field(default_factory=list)


class DiagnoseOutput(StrictModel):
    root_cause_summary: ShortText
    cause_class: Literal[
        "missing_check", "wrong_check", "unsafe_default", "logic_error", "dependency", "configuration"
    ]
    cause_paths: list[str] = Field(min_length=1, max_length=5)
    cause_start_lines: list[int] = Field(min_length=1, max_length=5)
    cause_end_lines: list[int] = Field(min_length=1, max_length=5)
    cause_symbol: str | None = None
    violated_expectation_ids: list[str] = Field(default_factory=list, max_length=6)
    strategy: str = Field(max_length=4000, description="What change fixes the cause, and why minimal.")
    constraints: list[ShortText] = Field(
        default_factory=list, max_length=8, description="Behaviour that must keep working."
    )
    files_expected: list[str] = Field(
        min_length=1, max_length=8, description="Files a patch is allowed to change."
    )
    tests_must_fail_before: list[ShortText] = Field(default_factory=list, max_length=6)
    tests_must_pass_after: list[ShortText] = Field(default_factory=list, max_length=6)
    related_sites: list[ShortText] = Field(
        default_factory=list, max_length=10, description="Other call sites sharing this cause."
    )


SPEC = AgentSpec(
    name=AgentName.DIAGNOSE,
    version="0.1.0",
    input_model=DiagnoseInput,
    output_model=DiagnoseOutput,
    tools=frozenset({
        "code.read_span", "code.search", "graph.neighbors", "expectations.for_subject",
        "findings.history", "static.analyze",
    }),
    sandbox_profile="none",
    network="none",
    write_access="none",
    budget_share=0.10,
    step_timeout_s=180,
    max_tool_calls=25,
    max_turns=12,
    prompt_ref="prompts/diagnose/v0.1.0.md",
    system_prompt=SYSTEM,
    max_output_tokens=6000,
)


def build_prompt(data: DiagnoseInput, intel: CodeIntel) -> str:
    return (
        "Find the root cause of this confirmed finding and write a remediation plan.\n\n"
        f"{data_block('finding', data.model_dump(mode='json'), provenance='trace_output')}\n\n"
        f"{data_block('expectations', [e.model_dump(mode='json') for e in intel.expectations()], provenance='code_intelligence')}\n\n"
        f"{data_block('snapshot_files', intel.snapshot.files()[:60], provenance='code_intelligence')}\n\n"
        "Trace from the affected handler to the function that should enforce the guarantee before "
        "deciding where the cause lives."
    )


def to_plan(
    out: DiagnoseOutput, data: DiagnoseInput, intel: CodeIntel
) -> tuple[RootCause, RemediationPlan, list[EvidenceRef]]:
    sha = intel.snapshot.commit_sha
    spans: list[EvidenceRef] = []
    n = min(len(out.cause_paths), len(out.cause_start_lines), len(out.cause_end_lines))
    for i in range(n):
        path = out.cause_paths[i]
        if not intel.snapshot.exists(path):
            continue
        limit = intel.snapshot.line_count(path)
        start = min(max(1, out.cause_start_lines[i]), limit)
        end = min(max(start, out.cause_end_lines[i]), limit)
        spans.append(
            EvidenceRef(
                path=path, sha=sha, span=SourceSpan(start_line=start, end_line=end),
                symbol=out.cause_symbol, provenance="code",
            )
        )
    if not spans:
        # Fall back to the affected handler so the record always cites real code.
        fallback = next((p for p in data.affected_paths if intel.snapshot.exists(p)), None)
        if fallback is None:
            raise ValueError("no valid cause span and no valid affected path")
        spans.append(
            EvidenceRef(
                path=fallback, sha=sha,
                span=SourceSpan(start_line=1, end_line=min(40, intel.snapshot.line_count(fallback))),
                provenance="code",
            )
        )
    known = {e.id for e in intel.expectations()}
    violated = [e for e in out.violated_expectation_ids if e in known] or [
        e for e in data.violated_expectation_ids if e in known
    ]
    root_cause = RootCause(
        finding_id=data.finding_id,
        summary=out.root_cause_summary,
        violated_expectation_ids=violated,
        cause_spans=spans,
        cause_class=CauseClass(out.cause_class),
    )
    # Enforced: planned files must exist in the snapshot, or be new test files.
    files = [
        p for p in out.files_expected
        if intel.snapshot.exists(p) or p.startswith("tests/")
    ]
    if not files:
        files = [spans[0].path or data.affected_paths[0]]
    plan = RemediationPlan(
        finding_id=data.finding_id,
        strategy=out.strategy,
        constraints=list(out.constraints),
        files_expected=files,
        test_plan=RemediationTestPlan(
            must_fail_before=list(out.tests_must_fail_before),
            must_pass_after=list(out.tests_must_pass_after),
        ),
    )
    related = [
        EvidenceRef(symbol=site[:200], provenance="agent_output") for site in out.related_sites
    ]
    return root_cause, plan, related
