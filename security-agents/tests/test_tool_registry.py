"""Tool registry: per-role allowlists, typed args, scope enforcement (SEC-002, SB-06)."""

from __future__ import annotations

import pytest

from security_agents.agents import ALL_SPECS
from security_agents.contracts import AgentName, ErrorCode, PlatformError, ScopeStatus
from security_agents.tools import AGENT_TOOL_ALLOWLIST, wire_name

from .conftest import TARGET_ID, make_ctx, make_scope

# The capability matrix from docs/07: (agent, tool) -> allowed?
EXPECTED_MATRIX: dict[str, dict[AgentName, bool]] = {
    "code.read_span": dict.fromkeys(AgentName, True),
    "code.search": {
        AgentName.SCOUT: True, AgentName.PROBE: False, AgentName.TRACE: True,
        AgentName.DIAGNOSE: True, AgentName.PATCH: True, AgentName.FORTIFY: True,
        AgentName.VERIFY: False,
    },
    "checks.run_template": {
        AgentName.SCOUT: False, AgentName.PROBE: True, AgentName.TRACE: False,
        AgentName.DIAGNOSE: False, AgentName.PATCH: False, AgentName.FORTIFY: False,
        AgentName.VERIFY: True,
    },
    "worktree.write_file": {
        AgentName.SCOUT: False, AgentName.PROBE: False, AgentName.TRACE: False,
        AgentName.DIAGNOSE: False, AgentName.PATCH: True, AgentName.FORTIFY: False,
        AgentName.VERIFY: False,
    },
    "tests.run": {
        AgentName.SCOUT: False, AgentName.PROBE: False, AgentName.TRACE: False,
        AgentName.DIAGNOSE: False, AgentName.PATCH: True, AgentName.FORTIFY: False,
        AgentName.VERIFY: True,
    },
    "patch.apply_fresh": {
        AgentName.SCOUT: False, AgentName.PROBE: False, AgentName.TRACE: False,
        AgentName.DIAGNOSE: False, AgentName.PATCH: False, AgentName.FORTIFY: False,
        AgentName.VERIFY: True,
    },
}


@pytest.mark.parametrize("tool,row", EXPECTED_MATRIX.items())
def test_allowlist_matches_specified_capability_matrix(tool, row):
    for agent, expected in row.items():
        assert (tool in AGENT_TOOL_ALLOWLIST[agent]) is expected, f"{agent.value}/{tool}"


# Documented permission profile per role (docs/07 capability matrix + agent contracts).
EXPECTED_PROFILE: dict[AgentName, dict[str, object]] = {
    AgentName.SCOUT: {"sandbox": "none", "network": "none", "write": "none", "may_execute": False},
    AgentName.PROBE: {"sandbox": "check-runner", "network": "target-only", "write": "out_dir", "may_execute": True},
    AgentName.TRACE: {"sandbox": "none", "network": "none", "write": "none", "may_execute": False},
    AgentName.DIAGNOSE: {"sandbox": "none", "network": "none", "write": "none", "may_execute": False},
    AgentName.PATCH: {"sandbox": "test-runner", "network": "none", "write": "worktree", "may_execute": True},
    AgentName.FORTIFY: {"sandbox": "none", "network": "none", "write": "none", "may_execute": False},
    AgentName.VERIFY: {"sandbox": "check-runner", "network": "target-only", "write": "none", "may_execute": True},
}

EXECUTION_TOOLS = frozenset({"checks.run_template", "tests.run", "patch.apply_fresh", "worktree.write_file"})


@pytest.mark.parametrize("agent", list(AgentName))
def test_each_role_has_its_documented_permission_profile(agent, registry):
    """Per-role permission assertions: sandbox profile, network, write access, execution rights."""
    spec = ALL_SPECS[agent]
    expected = EXPECTED_PROFILE[agent]
    assert spec.sandbox_profile == expected["sandbox"], agent.value
    assert spec.network == expected["network"], agent.value
    assert spec.write_access == expected["write"], agent.value
    tools = frozenset(registry.allowed_names(agent, spec.tools))
    assert tools, f"{agent.value} has no tools"
    assert bool(tools & EXECUTION_TOOLS) is expected["may_execute"], agent.value
    # Read-only roles can never reach a network or a sandbox, whatever a model asks for.
    if not expected["may_execute"]:
        assert spec.network == "none" and spec.write_access == "none"


def test_read_only_analysts_share_tools_but_differ_elsewhere(registry):
    """Scout, Diagnose and Fortify intentionally share the read-only catalog (docs/07).

    Their separation is enforced by distinct prompts, distinct output schemas and
    distinct orchestrator steps, not by the tool list. This pins that fact so a
    future change to one of them is a deliberate change.
    """
    trio = [AgentName.SCOUT, AgentName.DIAGNOSE, AgentName.FORTIFY]
    tool_sets = {a: frozenset(registry.allowed_names(a, ALL_SPECS[a].tools)) for a in trio}
    assert len(set(tool_sets.values())) == 1
    assert len({ALL_SPECS[a].system_prompt for a in trio}) == 3
    assert len({ALL_SPECS[a].output_model for a in trio}) == 3
    assert len({ALL_SPECS[a].input_model for a in trio}) == 3


def test_every_role_has_a_distinct_prompt_and_schema_pair():
    prompts = {a: ALL_SPECS[a].system_prompt for a in AgentName}
    assert len(set(prompts.values())) == len(AgentName)
    assert len({ALL_SPECS[a].output_model for a in AgentName}) == len(AgentName)
    assert len({ALL_SPECS[a].submit_tool_name() for a in AgentName}) == len(AgentName)


def test_execution_capable_roles_are_exactly_probe_patch_verify(registry):
    executors = {
        a for a in AgentName
        if frozenset(registry.allowed_names(a, ALL_SPECS[a].tools)) & EXECUTION_TOOLS
    }
    assert executors == {AgentName.PROBE, AgentName.PATCH, AgentName.VERIFY}


@pytest.mark.boundary
@pytest.mark.parametrize(
    "agent,forbidden",
    [
        (AgentName.SCOUT, "checks.run_template"),
        (AgentName.SCOUT, "worktree.write_file"),
        (AgentName.PROBE, "worktree.write_file"),
        (AgentName.PROBE, "tests.run"),
        (AgentName.TRACE, "checks.run_template"),
        (AgentName.DIAGNOSE, "tests.run"),
        (AgentName.PATCH, "checks.run_template"),
        (AgentName.PATCH, "patch.apply_fresh"),
        (AgentName.FORTIFY, "worktree.write_file"),
        (AgentName.VERIFY, "worktree.write_file"),
    ],
)
def test_forbidden_tool_raises_tool_not_allowed(agent, forbidden, registry, intel):
    """SB-06: an agent requesting a tool outside its allowlist is refused in code."""
    ctx = make_ctx(agent, intel=intel, scope=make_scope())
    with pytest.raises(PlatformError) as exc:
        registry.invoke(ctx, wire_name(forbidden), {})
    assert ErrorCode.TOOL_NOT_ALLOWED.value in str(exc.value)
    assert "tool.denied" in ctx.audit.actions()


def test_unknown_tool_is_refused(registry, intel):
    ctx = make_ctx(AgentName.SCOUT, intel=intel)
    with pytest.raises(PlatformError):
        registry.invoke(ctx, "definitely__not__a__tool", {})


def test_step_allowlist_narrows_agent_allowlist(registry, intel):
    ctx = make_ctx(AgentName.SCOUT, intel=intel)
    ctx.step_allowlist = frozenset({"code.read_span"})
    with pytest.raises(PlatformError) as exc:
        registry.invoke(ctx, wire_name("code.search"), {"pattern": "def "})
    assert ErrorCode.TOOL_NOT_ALLOWED.value in str(exc.value)


def test_kill_switch_blocks_every_tool(registry, intel):
    ctx = make_ctx(AgentName.SCOUT, intel=intel, kill_switch=lambda: True)
    with pytest.raises(PlatformError) as exc:
        registry.invoke(ctx, wire_name("code.read_span"), {"path": "payments_lite/app.py", "start_line": 1, "end_line": 5})
    assert ErrorCode.KILL_SWITCH.value in str(exc.value)


def test_schema_invalid_args_return_error_result_not_exception(registry, intel):
    ctx = make_ctx(AgentName.SCOUT, intel=intel)
    result = registry.invoke(ctx, wire_name("code.read_span"), {"path": "x.py", "start_line": 0})
    assert not result.ok and result.payload["error"] == ErrorCode.SCHEMA_INVALID.value
    assert "tool.schema_invalid" in ctx.audit.actions()


def test_extra_argument_is_rejected(registry, intel):
    ctx = make_ctx(AgentName.SCOUT, intel=intel)
    result = registry.invoke(
        ctx, wire_name("code.search"), {"pattern": "def ", "sudo": True}
    )
    assert not result.ok and result.payload["error"] == ErrorCode.SCHEMA_INVALID.value


def test_non_object_arguments_rejected(registry, intel):
    ctx = make_ctx(AgentName.SCOUT, intel=intel)
    with pytest.raises(PlatformError):
        registry.invoke(ctx, wire_name("code.search"), "pattern=def")


@pytest.mark.boundary
@pytest.mark.parametrize(
    "bad",
    [
        "../../etc/passwd",
        "/etc/passwd",
        "payments_lite/../../secrets.txt",
        "payments_lite/./../../x",
        "..",
        "",
        "payments_lite\\app.py",
        ".git/config",
    ],
)
def test_path_escape_is_refused(bad, registry, intel):
    """A model-supplied path that leaves the snapshot root is refused by policy."""
    ctx = make_ctx(AgentName.SCOUT, intel=intel)
    try:
        result = registry.invoke(
            ctx, wire_name("code.read_span"), {"path": bad, "start_line": 1, "end_line": 2}
        )
    except PlatformError as exc:
        assert exc.code is ErrorCode.SANDBOX_POLICY_VIOLATION, bad
        return
    assert not result.ok, bad
    assert result.payload["error"] in (
        ErrorCode.SANDBOX_POLICY_VIOLATION.value, "TOOL_ERROR", ErrorCode.SCHEMA_INVALID.value
    )


def test_read_span_returns_cited_content(registry, intel):
    ctx = make_ctx(AgentName.SCOUT, intel=intel)
    result = registry.invoke(
        ctx, wire_name("code.read_span"),
        {"path": "payments_lite/app.py", "start_line": 52, "end_line": 60},
    )
    assert result.ok
    assert result.payload["sha"] == intel.snapshot.commit_sha
    assert "get_payment" in result.payload["content"]


def test_graph_neighbors_exposes_sibling_difference(registry, intel):
    ctx = make_ctx(AgentName.SCOUT, intel=intel)
    weak = registry.invoke(ctx, wire_name("graph.neighbors"), {"symbol": "get_payment"}).payload
    sibling = registry.invoke(ctx, wire_name("graph.neighbors"), {"symbol": "list_refunds"}).payload
    weak_calls = " ".join(weak["callees"])
    sibling_calls = " ".join(sibling["callees"])
    assert "get_payment_for_customer" in sibling_calls
    assert "get_payment_for_customer" not in weak_calls


def test_tool_call_cap_enforced(registry, intel):
    ctx = make_ctx(AgentName.SCOUT, intel=intel)
    ctx.max_calls_per_tool = {"code.search": 1}
    first = registry.invoke(ctx, wire_name("code.search"), {"pattern": "def "})
    second = registry.invoke(ctx, wire_name("code.search"), {"pattern": "def "})
    assert first.ok and not second.ok and second.payload["error"] == "TOOL_CALL_LIMIT"


# --------------------------------------------------------------------------- scope


@pytest.mark.boundary
def test_check_run_against_out_of_scope_target_denied(registry, intel, library):
    """SB-01: a check against a target not in scope is denied before any sandbox exists."""
    class ExplodingRunner:
        def run(self, *a, **k):  # pragma: no cover - must never be reached
            raise AssertionError("check runner must not be reached when scope denies")

    ctx = make_ctx(
        AgentName.PROBE, intel=intel, scope=make_scope(),
        services={"check_runner": ExplodingRunner(), "checks": library},
    )
    with pytest.raises(PlatformError) as exc:
        registry.invoke(
            ctx, wire_name("checks.run_template"),
            {"template_ref": "access_control.ownership@1", "target_id": "tgt_not_mine", "parameters": {}},
        )
    assert ErrorCode.SCOPE_DENIED.value in str(exc.value)
    assert "tool.scope_denied" in ctx.audit.actions()


@pytest.mark.boundary
@pytest.mark.parametrize("status", [ScopeStatus.PENDING, ScopeStatus.EXPIRED, ScopeStatus.REVOKED])
def test_check_run_with_inactive_scope_denied(status, registry, intel, library):
    ctx = make_ctx(AgentName.PROBE, intel=intel, scope=make_scope(status=status),
                   services={"check_runner": object(), "checks": library})
    with pytest.raises(PlatformError) as exc:
        registry.invoke(
            ctx, wire_name("checks.run_template"),
            {"template_ref": "access_control.ownership@1", "target_id": TARGET_ID, "parameters": {}},
        )
    assert ErrorCode.SCOPE_DENIED.value in str(exc.value)


@pytest.mark.boundary
def test_check_run_with_category_outside_scope_denied(registry, intel, library):
    ctx = make_ctx(
        AgentName.PROBE, intel=intel,
        scope=make_scope(categories=["input_validation.bounds"]),
        services={"check_runner": object(), "checks": library},
    )
    with pytest.raises(PlatformError) as exc:
        registry.invoke(
            ctx, wire_name("checks.run_template"),
            {"template_ref": "access_control.ownership@1", "target_id": TARGET_ID, "parameters": {}},
        )
    assert ErrorCode.SCOPE_DENIED.value in str(exc.value)


def test_no_scope_at_all_denies_check_run(registry, intel, library):
    ctx = make_ctx(AgentName.PROBE, intel=intel, scope=None,
                   services={"check_runner": object(), "checks": library})
    with pytest.raises(PlatformError) as exc:
        registry.invoke(
            ctx, wire_name("checks.run_template"),
            {"template_ref": "access_control.ownership@1", "target_id": TARGET_ID, "parameters": {}},
        )
    assert ErrorCode.SCOPE_DENIED.value in str(exc.value)


# --------------------------------------------------------------------------- schemas


def test_tool_schemas_are_provider_valid(registry):
    import re

    for agent in AgentName:
        for schema in registry.schemas_for(agent, ALL_SPECS[agent].tools):
            assert re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", schema["name"]), schema["name"]
            assert schema["input_schema"]["additionalProperties"] is False
            assert schema["strict"] is True
            assert len(schema["description"]) < 1024


def test_registry_exposes_no_generic_execution_tool(registry):
    names = set()
    for agent in AgentName:
        names.update(registry.allowed_names(agent))
    for forbidden in ("shell", "bash", "http", "fetch", "exec", "fs.write", "eval"):
        assert not any(forbidden in n for n in names), forbidden
