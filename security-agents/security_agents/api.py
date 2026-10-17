"""`security_agents` public API (consumed by backend workers and code_review).

Published interfaces:
  * `build_orchestrator()` -> `.run(host)` — the backend worker entry point
    (`backend/INTEGRATION.md` §Alan); every model call goes through
    `host.llm()` and every record through the host.
  * `run_assessment(...)` / `Orchestrator` — the standalone assessment.
  * `run_agent_step(...)` — one agent step, for a worker that owns its own state.
  * `scope_guard.check(...)` — pure authorization decision.
  * `PatchWorktree` + `TestRunner` — the shared repair sandbox surface for
    `code_review` (Sai), so repair loops do not duplicate shell execution.
  * `ALL_SPECS` — the AgentSpec table, for UI/metadata.
"""

from __future__ import annotations

from .agents import ALL_SPECS
from .checks.library import CheckLibrary, default_library
from .contracts import SCHEMA_VERSION, AgentName
from .host_adapter import HostOrchestrator, build_orchestrator
from .intel import CodeIntel, CodeIntelligenceAdapter, LocalIntel
from .llm import LLMGateway, ProviderGateway
from .runtime import AgentSpec, StepOutcome
from .runtime import run_agent as run_agent_step
from .sandbox.driver import DockerSandboxDriver, LocalProcessDriver, SandboxDriver
from .sandbox.workspace import SnapshotHandle
from .scope_guard import ActionRequest, Decision
from .scope_guard import check as scope_check
from .tools import PatchWorktree, TestRunner, ToolContext, ToolRegistry, default_registry
from .workflow import AssessmentResult, Orchestrator, OrchestratorConfig


def run_assessment(
    config: OrchestratorConfig,
    *,
    intel: CodeIntel,
    gateway: LLMGateway,
    driver: SandboxDriver,
    library: CheckLibrary,
    workdir,
    **kwargs,
) -> AssessmentResult:
    return Orchestrator(
        config,
        intel=intel,
        gateway=gateway,
        driver=driver,
        library=library,
        workdir=workdir,
        **kwargs,
    ).run()


__all__ = [
    "ALL_SPECS",
    "SCHEMA_VERSION",
    "ActionRequest",
    "AgentName",
    "AgentSpec",
    "AssessmentResult",
    "CheckLibrary",
    "CodeIntel",
    "CodeIntelligenceAdapter",
    "Decision",
    "DockerSandboxDriver",
    "HostOrchestrator",
    "LLMGateway",
    "LocalIntel",
    "LocalProcessDriver",
    "Orchestrator",
    "OrchestratorConfig",
    "PatchWorktree",
    "ProviderGateway",
    "SandboxDriver",
    "SnapshotHandle",
    "StepOutcome",
    "TestRunner",
    "ToolContext",
    "ToolRegistry",
    "build_orchestrator",
    "default_library",
    "default_registry",
    "run_agent_step",
    "run_assessment",
    "scope_check",
]
