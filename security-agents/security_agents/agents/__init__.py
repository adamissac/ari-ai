"""The seven runtime security agents. Each module owns one agent's prompt, I/O
schemas, AgentSpec and the deterministic post-processing of its output."""

from ..contracts import AgentName
from ..runtime import AgentSpec
from . import diagnose, fortify, patch, probe, scout, trace, verify

ALL_SPECS: dict[AgentName, AgentSpec] = {
    AgentName.SCOUT: scout.SPEC,
    AgentName.PROBE: probe.SPEC,
    AgentName.TRACE: trace.SPEC,
    AgentName.DIAGNOSE: diagnose.SPEC,
    AgentName.PATCH: patch.SPEC,
    AgentName.FORTIFY: fortify.SPEC,
    AgentName.VERIFY: verify.SPEC,
}

__all__ = ["ALL_SPECS", "diagnose", "fortify", "patch", "probe", "scout", "trace", "verify"]
