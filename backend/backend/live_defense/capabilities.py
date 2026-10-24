"""Seven-agent capability registry derived from real AgentSpecs.

Read-only investigative vs code-changing / scoped-disruptive is computed from
``network`` and ``write_access`` on the live implementation, not from a prompt.
"""

from __future__ import annotations

from shared.assessment import SECURITY_AGENTS, AgentName
from shared.live_defense import (
    ORCHESTRATOR_VERSION,
    SEVEN_AGENT_NAMES,
    AgentCapability,
    AgentCapabilityClass,
    AgentCapabilityRegistry,
)

_NOTES = {
    AgentName.scout: "Read-only reconnaissance. Hypotheses are not confirmation.",
    AgentName.trace: "Read-only attack-path reconstruction after a confirmed Probe result.",
    AgentName.diagnose: "Read-only root-cause analysis. Cannot approve remediation.",
    AgentName.fortify: "Read-only hardening suggestions. Not executed configuration.",
    AgentName.probe: "Sandbox checks only with an active AuthorizedScope. No third-party hosts.",
    AgentName.patch: "Isolated worktree only. Never silent customer deploy or merge.",
    AgentName.verify: "Independent of Patch: fresh sandbox, no Patch transcript or worktree.",
}


def classify(*, network: str, write_access: str) -> AgentCapabilityClass:
    if write_access == "worktree":
        return AgentCapabilityClass.code_changing
    if network != "none":
        return AgentCapabilityClass.disruptive_scoped
    return AgentCapabilityClass.investigative_readonly


def load_registry() -> AgentCapabilityRegistry:
    """Build the registry from ``security_agents.agents.ALL_SPECS`` or fail closed."""
    try:
        from security_agents.agents import ALL_SPECS
    except ImportError:
        return AgentCapabilityRegistry(
            orchestrator_version=ORCHESTRATOR_VERSION,
            complete=False,
            agents=[],
            missing_names=[n.value for n in SEVEN_AGENT_NAMES],
            source="security_agents.agents.ALL_SPECS unavailable",
        )
    agents: list[AgentCapability] = []
    seen: set[AgentName] = set()
    specs_by_value = {getattr(key, "value", str(key)): spec for key, spec in ALL_SPECS.items()}
    for name in SEVEN_AGENT_NAMES:
        spec = specs_by_value.get(name.value)
        if spec is None:
            continue
        seen.add(name)
        agents.append(
            AgentCapability(
                name=name,
                spec_version=spec.version,
                capability_class=classify(network=spec.network, write_access=spec.write_access),
                tools=sorted(spec.tools),
                sandbox_profile=spec.sandbox_profile,
                network=spec.network,
                write_access=spec.write_access,
                notes=_NOTES[name],
            )
        )
    missing = [n.value for n in SEVEN_AGENT_NAMES if n not in seen]
    extra = [
        getattr(n, "value", str(n))
        for n in ALL_SPECS
        if getattr(n, "value", str(n)) not in {item.value for item in SEVEN_AGENT_NAMES}
        and getattr(n, "value", str(n)) in {item.value for item in SECURITY_AGENTS}
    ]
    return AgentCapabilityRegistry(
        orchestrator_version=ORCHESTRATOR_VERSION,
        complete=not missing,
        agents=agents,
        missing_names=[*missing, *extra],
        source="security_agents.agents.ALL_SPECS",
    )


def capability_for(
    name: AgentName, registry: AgentCapabilityRegistry | None = None
) -> AgentCapability:
    reg = registry or load_registry()
    for item in reg.agents:
        if item.name is name:
            return item
    raise KeyError(name)
