"""Fortify final-submission validity and recovery (M3 live run: Fortify ended SCHEMA_INVALID).

The live report from that run was not available, so these tests reproduce the failure
mechanism the code allows and that matches the reported shape (5 turns, 7 tool calls, then
SCHEMA_INVALID): a few evidence turns, then two submissions rejected by the strict output
model. The two rejections exercised here are the ones a model writing class-level sibling
hypotheses and countermeasures is most likely to hit without guidance: a CWE that MITRE marks
Discouraged (CWE-284) and a D3FEND id that is not in the pinned catalog (D3-RBAC).
"""

from __future__ import annotations

import copy
import re

import pytest

from security_agents.agents import fortify as fortify_agent
from security_agents.contracts import AgentName, Budget, ErrorCode, Usage
from security_agents.llm import FakeLLM, FakeTurn, ProviderGateway
from security_agents.runtime import run_agent
from security_agents.standards.fields import d3fend_entry
from security_agents.tools import default_registry

from .conftest import make_ctx, make_scope

SPEC = fortify_agent.SPEC
SUBMIT = SPEC.submit_tool_name()

VALID = {
    "recommendations": [
        {
            "category": "centralize_check",
            "recommendation": "Make require_owner a dependency every resource route uses.",
            "reference_path": "payments_lite/app.py",
            "reference_start_line": 74,
            "reference_end_line": 80,
            "effort": "small",
            "owner_review_note": "changes the store API; review call sites",
            "d3fend_technique": "D3-AMED",
        }
    ],
    "future_hypotheses": [
        {
            "weakness_class": "CWE-639",
            "title": "Sibling refund route may skip the ownership check",
            "rationale": "Same lookup pattern as the fixed payment detail handler.",
            "path": "payments_lite/app.py",
            "start_line": 90,
            "end_line": 100,
        }
    ],
    "monitoring_hints": ["Watch new resource routes in payments_lite/app.py"],
    "regression_test_names": [],
}


def with_cwe(cwe: str) -> dict:
    out = copy.deepcopy(VALID)
    out["future_hypotheses"][0]["weakness_class"] = cwe
    return out


def with_d3fend(technique: str) -> dict:
    out = copy.deepcopy(VALID)
    out["recommendations"][0]["d3fend_technique"] = technique
    return out


EVIDENCE_TURNS = [
    FakeTurn(
        tool_calls=[
            ("code__search", {"pattern": "def get_payment"}),
            ("code__search", {"pattern": "require_owner"}),
        ]
    ),
    FakeTurn(
        tool_calls=[
            ("code__search", {"pattern": "def get_refund"}),
            ("code__search", {"pattern": "store.get"}),
        ]
    ),
    FakeTurn(tool_calls=[("code__search", {"pattern": "APIRouter"})]),
]


def run(script: list, *, intel):
    gw = ProviderGateway(FakeLLM({AgentName.FORTIFY: script}), default_model="claude-opus-5-5")
    outcome = run_agent(
        SPEC,
        gateway=gw,
        registry=default_registry(),
        ctx=make_ctx(AgentName.FORTIFY, intel=intel, scope=make_scope()),
        task_prompt="propose prevention",
        budget=Budget(max_tokens=200_000, max_usd=5.0, max_wall_clock_s=60.0),
        assessment_usage=Usage(),
    )
    return outcome, gw


def test_the_two_likely_rejections_are_real_and_strict():
    """Both values are rejected by the output model (validation stays strict)."""
    with pytest.raises(Exception, match="Discouraged"):
        fortify_agent.FortifyOutput.model_validate(with_cwe("CWE-284"))
    with pytest.raises(Exception, match="not in D3FEND"):
        fortify_agent.FortifyOutput.model_validate(with_d3fend("D3-RBAC"))
    fortify_agent.FortifyOutput.model_validate(VALID)


def test_fortify_recovers_after_two_rejected_submissions(intel):
    """Reported shape: 3 evidence turns (5 tools) + 2 rejected submits = 5 turns, 7 tool calls.
    Before the fix the step ended SCHEMA_INVALID right there; now the third submit is accepted."""
    script = [
        *EVIDENCE_TURNS,
        FakeTurn(tool_calls=[(SUBMIT, with_cwe("CWE-284"))]),
        FakeTurn(tool_calls=[(SUBMIT, with_d3fend("D3-RBAC"))]),
        FakeTurn(tool_calls=[(SUBMIT, VALID)]),
    ]
    outcome, gw = run(script, intel=intel)
    assert outcome.ok, outcome.run.error_detail
    assert isinstance(outcome.output, fortify_agent.FortifyOutput)
    rejected = [t for t in outcome.record.tool_invocations if t.name == SUBMIT and not t.ok]
    assert rejected[0].summary["detail"].startswith("future_hypotheses.0.weakness_class")
    assert "D3-RBAC" in rejected[1].summary["detail"]
    assert len(gw.provider.calls) == 6


def test_fortify_still_fails_when_every_repair_is_invalid(intel):
    """Recovery is bounded: no fabricated success, strict validation preserved."""
    script = [*EVIDENCE_TURNS, *[FakeTurn(tool_calls=[(SUBMIT, with_cwe("CWE-284"))]) for _ in range(5)]]
    outcome, gw = run(script, intel=intel)
    assert not outcome.ok
    assert outcome.output is None
    assert outcome.run.error_code is ErrorCode.SCHEMA_INVALID
    assert "Discouraged" in (outcome.run.error_detail or "")
    assert len(gw.provider.calls) == len(EVIDENCE_TURNS) + 1 + SPEC.max_schema_repairs


def test_malformed_submissions_are_rejected_not_coerced(intel):
    """Missing required fields / extra fields fail validation; a later valid submit succeeds."""
    missing = {"future_hypotheses": [], "monitoring_hints": []}  # no recommendations
    extra = {**VALID, "notes": "free text the schema does not allow"}
    outcome, _ = run(
        [
            FakeTurn(tool_calls=[(SUBMIT, missing)]),
            FakeTurn(tool_calls=[(SUBMIT, extra)]),
            FakeTurn(tool_calls=[(SUBMIT, VALID)]),
        ],
        intel=intel,
    )
    assert outcome.ok
    details = [t.summary["detail"] for t in outcome.record.tool_invocations if t.name == SUBMIT and not t.ok]
    assert details[0].startswith("recommendations")
    assert "notes" in details[1]


def test_overlong_reply_without_submit_gets_a_chance_to_submit(intel):
    """A reply cut off at max_tokens with no submit is recoverable instead of an instant SCHEMA_INVALID."""
    script = [
        FakeTurn(text="long reasoning " * 50, stop_reason="max_tokens"),
        FakeTurn(tool_calls=[(SUBMIT, VALID)]),
    ]
    outcome, _ = run(script, intel=intel)
    assert outcome.ok, outcome.run.error_detail


def test_prompt_gives_the_finding_cwe_and_only_valid_standards_ids(intel):
    """Fortify is told the finding's own CWE, the Discouraged-CWE rule, and a D3FEND list that
    really exists in the pinned catalog (guards against prompt drift)."""
    data = fortify_agent.FortifyInput(
        assessment_id="asm_1",
        finding_id="fnd_1",
        verification_result_id="ver_1",
        root_cause_summary="handler skips require_owner",
        cause_class="missing_check",
        weakness_class="CWE-639",
    )
    prompt = fortify_agent.build_prompt(data, intel)
    assert '"weakness_class": "CWE-639"' in prompt
    system = fortify_agent.SYSTEM
    assert "CWE-284" in system and "Discouraged" in system
    ids = set(re.findall(r"\bD3-[A-Z]+\b", system))
    assert ids, "the prompt lists D3FEND ids"
    for technique in ids:
        d3fend_entry(technique)  # raises if the prompt names an id the validator would reject
    assert SPEC.max_schema_repairs >= 2
