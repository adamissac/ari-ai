# security-agents/

> **What exists: nothing yet (Phase 0).** Specs: [docs/07](../docs/07_SEVEN_AGENT_CYBERTEAM.md),
> [docs/08](../docs/08_AGENT_ORCHESTRATION.md), [docs/agents/](../docs/agents/AGENT_CONTRACT.md),
> boundaries [docs/15](../docs/15_SECURITY_BOUNDARIES.md).

## Purpose
Pillar 2: the seven runtime security agents (Scout, Probe, Trace, Diagnose,
Patch, Fortify, Verify), the orchestrator workflow definitions, the tool
registry, the scope guard, the sandbox driver and the reviewed check-template
library.

## Responsibilities
- `AgentSpec` runtime: agent loop, allowlisted tool calls, output validation,
  step budgets, recording.
- One module per agent with its own prompt, schemas, allowlist and budget.
- Deterministic orchestrator state machine + gates (hosted by `backend`).
- `scope_guard` (pure functions), `tool_registry`, `sandbox_driver`,
  `target_builder`.
- Check-template library: versioned, non-destructive, security-owner reviewed.

**Must not:** bypass the authorization service, expose generic shell/HTTP tools,
reference targets by host/URL, let model output change state, share mutable
state between Patch and Verify, contain third-party exploit content.

## Interfaces
| Interface | Consumers |
|---|---|
| `security_agents.workflow` (states, transitions, gates) | `backend` orchestration host |
| `security_agents.run_step(AgentStepJob)` | worker |
| `security_agents.scope_guard.check(...)` | backend scope API, tool registry, sandbox driver |
| `security_agents.sandbox` (profiles `test-runner`, `check-runner`, `target`) | code-review, Verify, Patch, Probe |
| Agent I/O schemas | `shared/` |

## Permissions summary
See the capability matrix in [docs/07](../docs/07_SEVEN_AGENT_CYBERTEAM.md) and
[TOOL_REGISTRY](../docs/agents/TOOL_REGISTRY.md). Changes to allowlists, scope
guard, sandbox config or verdict rules are safety-critical (two reviewers incl.
security owner).

## Dependencies
`shared/`; `backend` LLM gateway, persistence, artifacts; `code_intelligence.api`;
Docker Engine API (Python Docker SDK, proposed); pinned sandbox images (INFRA-005).

## Planned layout
```
security-agents/
  security_agents/
    runtime/        # AgentSpec, loop, recording
    agents/scout/ probe/ trace/ diagnose/ patch/ fortify/ verify/
    workflow/       # state machine definitions, gates
    tools/          # registry + tool implementations
    scope_guard.py
    sandbox/        # driver, profiles, network modes, reaper, target_builder
    checks/         # reviewed check templates (read-only category in MVP)
  tests/
```

## First tasks
SEC-001, SEC-002, SEC-003, then SEC-004 … SEC-013.

## Commands
None yet.
