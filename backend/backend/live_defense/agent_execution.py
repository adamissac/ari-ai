"""Phase 7C: run authorized investigative agents for the first-responder.

Scout (and Diagnose after Scout) execute the real ``security_agents`` loop against
an owner-attested mapped snapshot. Probe, Patch, Verify, and Trace stay gated:
this module does not widen their privileges. Typed output is persisted as
unverified evidence. LLM prose cannot confirm a threat.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Connection

from backend.artifacts import ArtifactStore
from backend.settings import get_settings
from shared.assessment import AgentName
from shared.base import utcnow
from shared.evidence import ArtifactKind
from shared.live_defense import (
    FIRST_RESPONDER_DEADLINE_S,
    FIRST_RESPONDER_MAX_USD,
    AgentExecutionRecord,
    AgentInvocationStatus,
    ExecutionIntegrity,
    FirstResponderDecision,
    FirstResponderInvocation,
)

log = logging.getLogger("backend.live_defense.agent_execution")

# Test hook. Never set in production code.
GATEWAY_OVERRIDE: Any | None = None

INVESTIGATIVE_LIVE = frozenset({AgentName.scout, AgentName.diagnose})


class PrerequisiteNotReady(RuntimeError):
    """Diagnose ran before Scout finished. Worker retries this."""


@dataclass(frozen=True)
class ExecutionOutcome:
    status: AgentInvocationStatus
    reason: str
    provider_mode: str
    execution: AgentExecutionRecord
    confirmed: bool = False


def _fake_scripts_root(snapshot_root: Path) -> Path:
    return snapshot_root


def _fake_gateway(snapshot_root: Path) -> Any:
    import security_agents
    from security_agents.llm import FakeLLM, ProviderGateway

    tests_dir = Path(security_agents.__file__).resolve().parents[1]
    if str(tests_dir) not in sys.path:
        sys.path.insert(0, str(tests_dir))
    from tests.fake_agents import all_scripts

    return ProviderGateway(FakeLLM(all_scripts(_fake_scripts_root(snapshot_root))))


class _BackendGateway:
    """Adapter so first-responder live calls go through ``backend.llm`` (ADR-0007)."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.mode = str(inner.provider_mode)

    def model_for(self, agent: Any) -> str:
        name = getattr(agent, "value", agent)
        return str(self._inner.model_for(str(name)))

    def complete(self, request: Any) -> Any:
        from security_agents.llm.types import LLMResponse, LLMUsage

        resp = self._inner.create_message(
            agent=getattr(request.agent, "value", str(request.agent)),
            system=request.system,
            messages=request.messages,
            tools=request.tools,
            max_tokens=request.max_tokens,
        )
        usage = resp.usage or {}
        return LLMResponse(
            content=list(resp.content),
            stop_reason=str(resp.stop_reason or "end_turn"),
            usage=LLMUsage(
                input_tokens=int(usage.get("input_tokens") or 0),
                output_tokens=int(usage.get("output_tokens") or 0),
                cache_read_input_tokens=int(usage.get("cache_read_input_tokens") or 0),
            ),
            model=str(resp.model),
            provider_mode=self.mode,  # type: ignore[arg-type]
            response_id=resp.id,
            stop_details=resp.stop_details,
        )

    def cost_usd(self, model: str, usage: Any) -> float:
        from backend.llm import cost_usd

        return cost_usd(
            model,
            {
                "input_tokens": getattr(usage, "input_tokens", 0),
                "output_tokens": getattr(usage, "output_tokens", 0),
                "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0),
            },
        )


def build_gateway(snapshot_root: Path) -> Any:
    if GATEWAY_OVERRIDE is not None:
        return GATEWAY_OVERRIDE()
    from backend import llm

    if llm.TRANSPORT_OVERRIDE is not None:
        return _fake_gateway(snapshot_root)
    if llm.llm_mode() == "live":
        return _BackendGateway(llm.build_gateway())
    raise RuntimeError("LLM_UNAVAILABLE: no first-responder provider (no key, not fake)")


def _binding_for(repo_id: str) -> dict[str, Any] | None:
    path = get_settings().repository_bindings_file
    if path is None or not Path(path).is_file():
        return None
    entries = json.loads(Path(path).read_text(encoding="utf-8") or "[]")
    return next((item for item in entries if item.get("repo_id") == repo_id), None)


def pin_snapshot(*, repo_id: str, commit_sha: str, snapshot_id: str, dest: Path) -> Any:
    """Materialize the mapped commit the same way host mode does."""
    from security_agents.sandbox.workspace import SnapshotHandle, copy_tree

    binding = _binding_for(repo_id)
    if binding is None:
        raise RuntimeError(
            "SNAPSHOT_NOT_READY: repository is not bound for first-responder execution"
        )
    local = Path(binding["local_path"]).expanduser().resolve()
    subdir = str(binding.get("subdir") or ".")
    raw = SnapshotHandle.from_git(
        local,
        commit_sha,
        subdir,
        dest / "checkout",
        snapshot_id=snapshot_id,
        repo_id=repo_id,
    )
    recipe = raw.root / "build_recipe.json"
    target_dir = None
    if recipe.is_file():
        target_dir = json.loads(recipe.read_text(encoding="utf-8")).get("target_dir")
    if not target_dir:
        return raw
    if str(target_dir).startswith("/") or ".." in Path(str(target_dir)).parts:
        raise RuntimeError(
            "SCHEMA_INVALID: build_recipe.json target_dir must stay inside the checkout"
        )
    root = dest / "snapshot"
    copy_tree(raw.root / str(target_dir), root)
    shutil.copy2(recipe, root / "build_recipe.json")
    for path in root.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    return SnapshotHandle(
        snapshot_id=snapshot_id,
        repo_id=repo_id,
        commit_sha=raw.commit_sha,
        root=root,
        pinned_by="git",
    )


def _labels_path(snapshot: Any) -> Path | None:
    env = os.environ.get("SECURITY_AGENTS_LABELS")
    if env:
        path = Path(env)
        return path if path.is_file() else None
    candidate = snapshot.root / "labels.yaml"
    if candidate.is_file():
        return candidate
    parent = snapshot.root.parent / "labels.yaml"
    return parent if parent.is_file() else None


def _recipe_strip_prefix(snapshot: Any) -> str | None:
    """Match host/CLI: labels.yaml paths keep target_dir/; the snapshot root does not."""
    recipe_path = snapshot.root / "build_recipe.json"
    if not recipe_path.is_file():
        return None
    try:
        recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    target_dir = recipe.get("target_dir")
    if not target_dir:
        return None
    return f"{target_dir}/"


def load_intel(snapshot: Any) -> Any:
    from security_agents.intel import LocalIntel, load_expectations

    labels = _labels_path(snapshot)
    expectations = None
    if labels is not None:
        expectations = load_expectations(
            labels,
            snapshot_id=snapshot.snapshot_id,
            commit_sha=snapshot.commit_sha,
            strip_prefix=_recipe_strip_prefix(snapshot),
        )
    return LocalIntel(snapshot, expectations=expectations)


def _sa_name(agent: AgentName) -> Any:
    from security_agents.contracts import AgentName as SAName

    return SAName(agent.value)


def _tool_context(
    agent: AgentName, intel: Any, *, assessment_id: str, run_id: str, cancelled: Any
) -> Any:
    from security_agents.intel import FindingsHistory
    from security_agents.tools import ToolContext

    return ToolContext(
        assessment_id=assessment_id,
        agent=_sa_name(agent),
        run_id=run_id,
        step_key=f"first-responder:{agent.value}",
        read_root=intel.snapshot.root,
        services={"intel": intel, "history": FindingsHistory()},
        kill_switch=cancelled,
    )


def _persist_json(conn: Connection, project_id: str, value: Any, kind: ArtifactKind) -> str:
    return ArtifactStore().put_json(conn, value, kind=kind, project_id=project_id).id


def _record(
    *,
    provider_mode: str,
    model_id: str | None,
    cost_usd: float | None,
    latency_ms: int,
    llm_turns: int | None,
    tool_call_count: int | None,
    started_at: Any,
    ended_at: Any,
    transcript_id: str | None,
    output_id: str | None,
    error_code: str | None,
    typed_output: bool,
    hypothesis_count: int | None,
    integrity: ExecutionIntegrity,
) -> AgentExecutionRecord:
    return AgentExecutionRecord(
        provider_mode=provider_mode if provider_mode in {"fake", "live", "none"} else "none",
        model_id=model_id,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        llm_turns=llm_turns,
        tool_call_count=tool_call_count,
        started_at=started_at,
        ended_at=ended_at,
        transcript_artifact_id=transcript_id,
        output_artifact_id=output_id,
        error_code=error_code,
        typed_output=typed_output,
        hypothesis_count=hypothesis_count,
        execution_integrity=integrity,
    )


def _scout_input(decision: FirstResponderDecision, intel: Any) -> Any:
    from security_agents.agents import scout as scout_agent
    from security_agents.checks.library import default_library

    library = default_library()
    categories = sorted(library.categories())
    return scout_agent.ScoutInput(
        assessment_id=decision.id,
        snapshot_id=intel.snapshot.snapshot_id,
        commit_sha=intel.snapshot.commit_sha,
        expectation_ids=[e.id for e in intel.expectations()],
        max_hypotheses=5,
        available_check_categories=categories,
    )


def _diagnose_input(decision: FirstResponderDecision, scout_output: dict[str, Any]) -> Any:
    from security_agents.agents import diagnose as diagnose_agent

    hypotheses = list(scout_output.get("hypotheses") or [])
    if not hypotheses:
        raise RuntimeError("Diagnose requires Scout hypotheses; none were persisted")
    top = hypotheses[0]
    cited = top.get("cited_spans") or []
    paths = [str(item.get("path")) for item in cited if item.get("path")]
    return diagnose_agent.DiagnoseInput(
        assessment_id=decision.id,
        finding_id=str(top.get("id") or "fnd_first_responder_unverified"),
        weakness_class=str(top.get("weakness_class") or "CWE-639"),
        hypothesis_title=str(top.get("title") or "Scout hypothesis (unverified)"),
        severity_level="unverified",
        impact_summary=(
            "First-responder Diagnose input is a Scout hypothesis, not a confirmed finding. "
            "Do not treat this as independent verification."
        ),
        affected_paths=paths[:8],
        violated_expectation_ids=list(top.get("expectation_ids") or [])[:6],
    )


def run_investigative(
    *,
    agent: AgentName,
    decision: FirstResponderDecision,
    invocation: FirstResponderInvocation,
    repo_id: str,
    commit_sha: str,
    snapshot_id: str,
    scout_output: dict[str, Any] | None,
    cancelled: Any,
) -> ExecutionOutcome:
    """Execute Scout or Diagnose. Never sets confirmation=confirmed."""
    started = utcnow()
    t0 = time.monotonic()
    work = Path(tempfile.mkdtemp(prefix=f"fr-{agent.value}-"))
    try:
        snapshot = pin_snapshot(
            repo_id=repo_id, commit_sha=commit_sha, snapshot_id=snapshot_id, dest=work
        )
        intel = load_intel(snapshot)
        gateway = build_gateway(snapshot.root)
        from security_agents.agents import ALL_SPECS
        from security_agents.agents import diagnose as diagnose_agent
        from security_agents.agents import scout as scout_agent
        from security_agents.contracts import Budget
        from security_agents.runtime import run_agent
        from security_agents.tools import default_registry

        spec = ALL_SPECS[_sa_name(agent)]
        if agent is AgentName.scout:
            data = _scout_input(decision, intel)
            prompt = scout_agent.build_prompt(data, intel)
        elif agent is AgentName.diagnose:
            if not scout_output:
                raise PrerequisiteNotReady("Diagnose waiting for Scout hypotheses")
            data = _diagnose_input(decision, scout_output)
            prompt = (
                "This input is a first-responder Scout hypothesis, not a confirmed finding.\n\n"
                + diagnose_agent.build_prompt(data, intel)
            )
        else:
            raise RuntimeError(f"{agent.value} is not a Phase 7C live investigative agent")

        ctx = _tool_context(
            agent,
            intel,
            assessment_id=decision.id,
            run_id=invocation.id,
            cancelled=cancelled,
        )
        outcome = run_agent(
            spec,
            gateway=gateway,
            registry=default_registry(),
            ctx=ctx,
            task_prompt=prompt,
            budget=Budget(
                max_tokens=80_000,
                max_usd=min(FIRST_RESPONDER_MAX_USD, 1.5),
                max_wall_clock_s=float(min(FIRST_RESPONDER_DEADLINE_S, spec.step_timeout_s)),
            ),
            input_ref=f"first-responder:{decision.id}:{agent.value}",
            cancelled=cancelled,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        provider_mode = str(outcome.record.provider_mode)
        usage = outcome.record.usage
        from backend.db import transaction as db_transaction

        with db_transaction() as persist:
            transcript_id = _persist_json(
                persist,
                decision.project_id,
                outcome.record.to_json(),
                ArtifactKind.llm_transcript,
            )
        hypotheses: list[dict[str, Any]] = []
        integrity = ExecutionIntegrity.failed
        typed = outcome.output is not None
        if agent is AgentName.scout and isinstance(outcome.output, scout_agent.ScoutOutput):
            hyps = scout_agent.to_hypotheses(outcome.output, data, intel)
            hypotheses = [h.model_dump(mode="json") for h in hyps]
            integrity = ExecutionIntegrity.checked if hyps else ExecutionIntegrity.failed
        elif agent is AgentName.diagnose and outcome.output is not None:
            try:
                _plan = diagnose_agent.to_plan(outcome.output, data, intel)
                integrity = ExecutionIntegrity.checked if _plan[2] else ExecutionIntegrity.failed
            except Exception:
                integrity = ExecutionIntegrity.failed
        payload = {
            "agent": agent.value,
            "ok": outcome.ok,
            "typed_output": typed,
            "output": outcome.output.model_dump(mode="json")
            if outcome.output is not None
            else None,
            "hypotheses": hypotheses,
            "execution_integrity": integrity.value,
            "llm_prose_is_not_confirmation": True,
            "predicted_probability": None,
            "error_code": outcome.run.error_code.value if outcome.run.error_code else None,
            "error_detail": outcome.run.error_detail,
        }
        with db_transaction() as persist:
            output_id = _persist_json(
                persist, decision.project_id, payload, ArtifactKind.tool_output
            )
        error_code = outcome.run.error_code.value if outcome.run.error_code else None
        execution = _record(
            provider_mode=provider_mode,
            model_id=outcome.record.model,
            cost_usd=float(usage.usd) if usage else 0.0,
            latency_ms=latency_ms,
            llm_turns=outcome.run.llm_turns,
            tool_call_count=outcome.run.tool_calls,
            started_at=started,
            ended_at=utcnow(),
            transcript_id=transcript_id,
            output_id=output_id,
            error_code=error_code,
            typed_output=typed,
            hypothesis_count=len(hypotheses) if agent is AgentName.scout else None,
            integrity=integrity,
        )
        if not outcome.ok:
            return ExecutionOutcome(
                status=AgentInvocationStatus.failed,
                reason=(
                    f"{agent.value} agent loop failed ({error_code or 'unknown'}). "
                    "Not a confirmed threat."
                )[:2000],
                provider_mode=provider_mode if provider_mode in {"fake", "live"} else "none",
                execution=execution,
            )
        reason = (
            f"{agent.value} executed a real agent loop ({provider_mode}). "
            f"execution_integrity={integrity.value}. "
            "Typed output is not independent verification and not a confirmed threat."
        )
        return ExecutionOutcome(
            status=AgentInvocationStatus.executed,
            reason=reason[:2000],
            provider_mode=provider_mode if provider_mode in {"fake", "live"} else "none",
            execution=execution,
        )
    except PrerequisiteNotReady:
        raise
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        code = "LLM_UNAVAILABLE" if "LLM_UNAVAILABLE" in str(exc) else type(exc).__name__
        log.exception("first-responder %s execution failed", agent.value)
        execution = _record(
            provider_mode="none",
            model_id=None,
            cost_usd=None,
            latency_ms=latency_ms,
            llm_turns=None,
            tool_call_count=None,
            started_at=started,
            ended_at=utcnow(),
            transcript_id=None,
            output_id=None,
            error_code=code[:200],
            typed_output=False,
            hypothesis_count=None,
            integrity=ExecutionIntegrity.failed,
        )
        return ExecutionOutcome(
            status=AgentInvocationStatus.failed,
            reason=f"{agent.value} did not execute: {str(exc)[:400]}",
            provider_mode="none",
            execution=execution,
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)


def load_scout_output(conn: Connection, artifact_id: str | None) -> dict[str, Any] | None:
    if not artifact_id:
        return None
    try:
        _meta, data = ArtifactStore().get(conn, artifact_id)
    except (KeyError, OSError):
        return None
    try:
        payload = json.loads(data.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None
