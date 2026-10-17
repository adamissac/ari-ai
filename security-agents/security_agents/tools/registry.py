"""Tool registry: per-agent static allowlists, typed arguments, scope enforcement.

Enforcement order for every model-requested call
(docs/architecture/sandbox-and-authorization):

    kill switch -> agent allowlist -> step allowlist -> argument schema
    -> scope_guard (network-capable tools) -> call budget -> handler

The model cannot add tools, cannot name a host, and cannot reach a handler
whose allowlist entry is missing. Every denial raises a `PlatformError` with a
catalog code and is audited.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from ..contracts import AgentName, AuthorizedScope, ErrorCode, PlatformError, StrictModel
from ..redact import redact
from ..scope_guard import ActionRequest, Decision
from ..scope_guard import check as scope_check

SideEffects = Literal["none", "sandbox_exec", "worktree_write", "network_target_only"]

# Canonical capability matrix (docs/agents/TOOL_REGISTRY.md). Safety-critical:
# changes need security-owner review per docs/15.
AGENT_TOOL_ALLOWLIST: dict[AgentName, frozenset[str]] = {
    AgentName.SCOUT: frozenset(
        {
            "code.read_span",
            "code.search",
            "graph.neighbors",
            "expectations.for_subject",
            "findings.history",
            "static.analyze",
        }
    ),
    AgentName.PROBE: frozenset(
        {
            "code.read_span",
            "expectations.for_subject",
            "checks.list_templates",
            "checks.run_template",
        }
    ),
    AgentName.TRACE: frozenset(
        {
            "code.read_span",
            "code.search",
            "graph.neighbors",
            "expectations.for_subject",
            "findings.history",
        }
    ),
    AgentName.DIAGNOSE: frozenset(
        {
            "code.read_span",
            "code.search",
            "graph.neighbors",
            "expectations.for_subject",
            "findings.history",
            "static.analyze",
        }
    ),
    AgentName.PATCH: frozenset(
        {
            "code.read_span",
            "code.search",
            "graph.neighbors",
            "expectations.for_subject",
            "worktree.write_file",
            "worktree.diff",
            "tests.run",
        }
    ),
    AgentName.FORTIFY: frozenset(
        {
            "code.read_span",
            "code.search",
            "graph.neighbors",
            "expectations.for_subject",
            "findings.history",
            "static.analyze",
        }
    ),
    AgentName.VERIFY: frozenset(
        {
            "code.read_span",
            "expectations.for_subject",
            "static.analyze",
            "checks.list_templates",
            "checks.run_template",
            "tests.run",
            "patch.apply_fresh",
        }
    ),
}


def wire_name(name: str) -> str:
    """Provider tool names allow [a-zA-Z0-9_-] only; dots become double underscores."""
    return name.replace(".", "__")


def tool_name(wire: str) -> str:
    return wire.replace("__", ".")


@dataclass
class AuditSink:
    """Collects audit records; the workflow hash-chains and persists them."""

    records: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, action: str, **details: Any) -> None:
        self.records.append({"action": action, "at": datetime.now(UTC).isoformat(), **redact(details)})

    def actions(self) -> list[str]:
        return [r["action"] for r in self.records]


@dataclass
class ToolContext:
    """Everything a tool handler may touch. Handlers receive no globals."""

    assessment_id: str
    agent: AgentName
    run_id: str
    step_key: str
    read_root: Path
    services: dict[str, Any] = field(default_factory=dict)
    scope: AuthorizedScope | None = None
    org_member_count: int = 1
    audit: AuditSink = field(default_factory=AuditSink)
    kill_switch: Callable[[], bool] = lambda: False
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    step_allowlist: frozenset[str] | None = None
    max_calls_per_tool: dict[str, int] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)

    def service(self, name: str) -> Any:
        svc = self.services.get(name)
        if svc is None:
            raise PlatformError(ErrorCode.CONFLICT_STATE, f"service {name!r} is not wired for this step")
        return svc


@dataclass(frozen=True)
class ToolDef:
    name: str
    version: str
    description: str
    args_model: type[StrictModel]
    side_effects: SideEffects
    requires_scope: bool
    handler: Callable[[ToolContext, Any], dict[str, Any]]
    timeout_s: float = 120.0
    max_output_bytes: int = 24_000
    scope_action: Literal["run_check", "attach_network", "build_target"] | None = None
    category_from: str | None = None  # args field holding the check category
    target_from: str | None = None  # args field holding the target id

    def schema(self) -> dict[str, Any]:
        """Anthropic tool definition. `strict` keeps model arguments schema-valid."""
        from .strict_schema import tool_input_schema

        raw = self.args_model.model_json_schema()
        raw["additionalProperties"] = False
        raw.setdefault("required", [])
        schema, strict = tool_input_schema(raw)
        return {
            "name": wire_name(self.name),
            "description": f"{self.description} (v{self.version}; side effects: {self.side_effects})",
            "input_schema": schema,
            "strict": strict,
        }


@dataclass
class ToolResult:
    name: str
    ok: bool
    payload: dict[str, Any]

    def to_text(self, limit: int) -> str:
        text = json.dumps(self.payload, default=str, sort_keys=False)
        if len(text) > limit:
            text = text[:limit] + '... [truncated]"}'
        return text


class ToolRegistry:
    def __init__(self, tools: dict[str, ToolDef]) -> None:
        self._tools = dict(tools)

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def allowed_names(self, agent: AgentName, step_allowlist: frozenset[str] | None = None) -> list[str]:
        allowed = AGENT_TOOL_ALLOWLIST.get(agent, frozenset())
        if step_allowlist is not None:
            allowed = allowed & step_allowlist
        return sorted(n for n in allowed if n in self._tools)

    def schemas_for(
        self, agent: AgentName, step_allowlist: frozenset[str] | None = None
    ) -> list[dict[str, Any]]:
        return [self._tools[n].schema() for n in self.allowed_names(agent, step_allowlist)]

    # ------------------------------------------------------------------ invoke

    def invoke(self, ctx: ToolContext, wire_tool: str, raw_args: Any) -> ToolResult:
        """Run one model-requested tool call under full enforcement."""
        name = tool_name(str(wire_tool))

        if ctx.kill_switch():
            ctx.audit.emit("tool.kill_switch", agent=ctx.agent.value, tool=name, run_id=ctx.run_id)
            raise PlatformError(ErrorCode.KILL_SWITCH, "assessments are paused")

        allowed = AGENT_TOOL_ALLOWLIST.get(ctx.agent, frozenset())
        if name not in allowed:
            ctx.audit.emit(
                "tool.denied",
                agent=ctx.agent.value,
                tool=name,
                reason="not_in_agent_allowlist",
                run_id=ctx.run_id,
            )
            raise PlatformError(ErrorCode.TOOL_NOT_ALLOWED, f"{ctx.agent.value} may not call {name}")
        if ctx.step_allowlist is not None and name not in ctx.step_allowlist:
            ctx.audit.emit(
                "tool.denied",
                agent=ctx.agent.value,
                tool=name,
                reason="not_in_step_allowlist",
                run_id=ctx.run_id,
            )
            raise PlatformError(ErrorCode.TOOL_NOT_ALLOWED, f"{name} is not allowed in this step")

        tool = self._tools.get(name)
        if tool is None:
            raise PlatformError(ErrorCode.TOOL_NOT_ALLOWED, f"tool {name} is not registered")

        if not isinstance(raw_args, dict):
            raise PlatformError(ErrorCode.SCHEMA_INVALID, "tool arguments must be a JSON object")
        try:
            args = tool.args_model.model_validate(raw_args)
        except ValidationError as exc:
            ctx.audit.emit(
                "tool.schema_invalid",
                agent=ctx.agent.value,
                tool=name,
                run_id=ctx.run_id,
                errors=exc.error_count(),
            )
            return ToolResult(
                name=name,
                ok=False,
                payload={"error": ErrorCode.SCHEMA_INVALID.value, "detail": _compact_errors(exc)},
            )

        if tool.requires_scope:
            decision = self._scope_decision(ctx, tool, args)
            if not decision.allowed:
                ctx.audit.emit(
                    "tool.scope_denied",
                    agent=ctx.agent.value,
                    tool=name,
                    run_id=ctx.run_id,
                    reason_code=decision.reason_code,
                    scope_id=decision.scope_id,
                    detail=decision.detail,
                )
                raise PlatformError(
                    ErrorCode.SCOPE_DENIED, f"{name}: {decision.reason_code} {decision.detail}".strip()
                )
            ctx.artifacts["last_scope_decision"] = decision

        used = ctx.counters.get(name, 0)
        cap = ctx.max_calls_per_tool.get(name)
        if cap is not None and used >= cap:
            return ToolResult(
                name=name,
                ok=False,
                payload={"error": "TOOL_CALL_LIMIT", "detail": f"{name} may be called at most {cap} times"},
            )
        ctx.counters[name] = used + 1

        try:
            payload = tool.handler(ctx, args)
            ok = not bool(payload.get("error"))
        except PlatformError:
            raise
        except Exception as exc:
            ctx.audit.emit(
                "tool.error",
                agent=ctx.agent.value,
                tool=name,
                run_id=ctx.run_id,
                error=f"{type(exc).__name__}: {exc}"[:300],
            )
            return ToolResult(
                name=name,
                ok=False,
                payload={"error": "TOOL_ERROR", "detail": f"{type(exc).__name__}: {exc}"[:500]},
            )

        ctx.audit.emit(
            "tool.called",
            agent=ctx.agent.value,
            tool=name,
            run_id=ctx.run_id,
            side_effects=tool.side_effects,
            ok=ok,
            args=redact(args.model_dump(mode="json")),
        )
        return ToolResult(name=name, ok=ok, payload=payload)

    def _scope_decision(self, ctx: ToolContext, tool: ToolDef, args: StrictModel) -> Decision:
        data = args.model_dump()
        target_id = str(data.get(tool.target_from)) if tool.target_from else None
        category: str | None = None
        if tool.category_from:
            raw = data.get(tool.category_from)
            if isinstance(raw, str) and raw:
                # `template_ref` carries `category@version`; the category is the id part.
                category = raw.split("@", 1)[0]
        return scope_check(
            ctx.scope,
            ActionRequest(
                action=tool.scope_action or "run_check",
                target_id=target_id,
                check_category=category,
                agent=ctx.agent,
            ),
            ctx.now(),
            org_member_count=ctx.org_member_count,
        )


def _compact_errors(exc: ValidationError) -> str:
    parts = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:6]]
    return "; ".join(parts)[:500]
