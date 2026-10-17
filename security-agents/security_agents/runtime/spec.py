"""`AgentSpec`: the declarative definition of one runtime agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..contracts import AgentName, StrictModel

SandboxProfileName = Literal["none", "test-runner", "check-runner"]
NetworkMode = Literal["none", "target-only"]
WriteAccess = Literal["none", "out_dir", "worktree"]


@dataclass(frozen=True)
class AgentSpec:
    """Values for one agent (docs/agents/AGENT_CONTRACT.md §AgentSpec).

    The spec is the single place that says what an agent may do. The runtime
    derives the provider tool schemas, the budget slice and the stop conditions
    from it; the tool registry independently enforces the allowlist, so a spec
    that claims a tool the registry does not grant still cannot call it.
    """

    name: AgentName
    version: str
    input_model: type[StrictModel]
    output_model: type[StrictModel]
    tools: frozenset[str]
    sandbox_profile: SandboxProfileName
    network: NetworkMode
    write_access: WriteAccess
    budget_share: float
    step_timeout_s: int
    max_tool_calls: int
    max_turns: int
    prompt_ref: str
    system_prompt: str
    max_calls_per_tool: dict[str, int] = field(default_factory=dict)
    effort: str = "medium"
    max_output_tokens: int = 8000

    def submit_tool_name(self) -> str:
        return f"submit_{self.name.value}_output"
