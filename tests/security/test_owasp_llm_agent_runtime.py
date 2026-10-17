"""OWASP LLM Top 10 2026 evidence for the seven runtime security agents (security-agents/)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from security_agents.checks.library import default_library
from security_agents.contracts import (
    AgentName,
    AuthorizedScope,
    ErrorCode,
    PlatformError,
    ScopeStatus,
    ScopeTarget,
)
from security_agents.redact import REDACTED, redact
from security_agents.standards.roe import build_roe
from security_agents.tools import ToolContext, default_registry, wire_name

NOW = datetime.now(UTC)
TARGET = "tgt_payments_lite"


def _scope() -> AuthorizedScope:
    library = default_library()
    return AuthorizedScope(
        id="scp_owasp",
        project_id="prj_owasp",
        name="payments-lite sandbox",
        targets=[
            ScopeTarget(
                target_id=TARGET,
                repo_id="rep_payments_lite",
                build_recipe_ref="build_recipe.json",
                exposed_ports=[8000],
            )
        ],
        allowed_check_categories=sorted(library.categories()),
        status=ScopeStatus.ACTIVE,
        requested_by="usr_requester",
        approved_by="usr_approver",
        approved_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
    )


def _ctx(
    agent: AgentName, tmp_path: Path, runner: object, scope: AuthorizedScope | None
) -> ToolContext:
    return ToolContext(
        assessment_id="asm_owasp",
        agent=agent,
        run_id="run_owasp",
        step_key="step",
        read_root=tmp_path,
        services={"check_runner": runner, "checks": default_library()},
        scope=scope,
    )


class MustNotRun:
    def run(self, *args, **kwargs):
        raise AssertionError("the check runner must not be reached")


CHECK = {"template_ref": "access_control.ownership@1", "target_id": TARGET, "parameters": {}}


@pytest.mark.owasp_llm("LLM01:2026")
@pytest.mark.owasp_llm("LLM03:2026")
def test_security_agent_cannot_call_a_tool_outside_its_role(tmp_path):
    ctx = _ctx(AgentName.SCOUT, tmp_path, MustNotRun(), _scope())
    with pytest.raises(PlatformError) as error:
        default_registry().invoke(ctx, wire_name("checks.run_template"), CHECK)
    assert error.value.code is ErrorCode.TOOL_NOT_ALLOWED


@pytest.mark.owasp_llm("LLM03:2026")
def test_probe_check_without_rules_of_engagement_fails_closed(tmp_path):
    ctx = _ctx(AgentName.PROBE, tmp_path, MustNotRun(), _scope())
    with pytest.raises(PlatformError) as error:
        default_registry().invoke(ctx, wire_name("checks.run_template"), CHECK)
    assert error.value.code is ErrorCode.SCOPE_DENIED
    assert "tool.roe_denied" in ctx.audit.actions()


@pytest.mark.owasp_llm("LLM01:2026")
@pytest.mark.owasp_llm("LLM03:2026")
def test_probe_check_against_an_unlisted_target_is_denied_even_with_rules_of_engagement(tmp_path):
    scope = _scope()
    ctx = _ctx(AgentName.PROBE, tmp_path, MustNotRun(), scope)
    ctx.roe = build_roe(scope, default_library().list_public())
    with pytest.raises(PlatformError) as error:
        default_registry().invoke(
            ctx, wire_name("checks.run_template"), {**CHECK, "target_id": "tgt_someone_else"}
        )
    assert error.value.code is ErrorCode.SCOPE_DENIED


@pytest.mark.owasp_llm("LLM07:2026")
@pytest.mark.owasp_llm("LLM10:2026")
def test_security_agent_output_cannot_carry_a_score_or_level():
    from security_agents.agents.trace import TraceOutput

    metrics = [
        {"metric": m, "value": v, "rationale": "r"}
        for m, v in zip(("AV", "AC", "PR", "UI", "S", "C", "I", "A"), "NLLNUHNN", strict=True)
    ]
    base = {
        "steps": [{"description": "Protected data is reachable", "verified": False}],
        "impact_summary": "Cross-owner access",
        "cvss_base_metrics": metrics,
        "severity_rationale": "r",
    }
    TraceOutput.model_validate(base)
    for field, value in (("cvss_base_score", 10.0), ("level", "critical"), ("rating", "critical")):
        with pytest.raises(ValidationError):
            TraceOutput.model_validate({**base, field: value})


@pytest.mark.owasp_llm("LLM07:2026")
def test_invented_weakness_identifier_is_rejected_before_validation():
    from security_agents.agents.probe import ProbeInput

    with pytest.raises(ValidationError, match="SCHEMA_INVALID"):
        ProbeInput(
            assessment_id="a",
            hypothesis_id="h",
            scope_id="s",
            target_id=TARGET,
            hypothesis_title="Finding",
            weakness_class="CWE-99999",
            expected_invariant="Owner only",
            suggested_check_category="access_control.ownership",
        )


@pytest.mark.owasp_llm("LLM02:2026")
def test_security_agent_records_are_redacted():
    token = "ghp_" + "A1b2C3d4" * 5
    cleaned = redact({"tool_result": f"Authorization: Bearer {token}", "nested": [{"key": token}]})
    assert token not in str(cleaned)
    assert REDACTED in str(cleaned)
