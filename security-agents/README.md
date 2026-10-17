# security-agents/

Pillar 2: the seven runtime security agents (Scout, Probe, Trace, Diagnose,
Patch, Fortify, Verify), the deterministic orchestrator, the tool registry, the
scope guard, the sandbox driver and the reviewed check-template library.

Specs: [docs/07](../docs/07_SEVEN_AGENT_CYBERTEAM.md),
[docs/08](../docs/08_AGENT_ORCHESTRATION.md),
[docs/agents/](../docs/agents/AGENT_CONTRACT.md),
boundaries [docs/15](../docs/15_SECURITY_BOUNDARIES.md).

> **Runtime agents are product features.** They are not Claude Code subagents
> and not the six developers' assistants.

## What exists now

| Area | Module | Status |
|---|---|---|
| Agent loop, budgets, recording | `security_agents/runtime/` | implemented, tested |
| Seven agent specs, prompts, I/O schemas | `security_agents/agents/` | implemented, tested |
| Tool registry + capability matrix | `security_agents/tools/registry.py` | implemented, tested |
| Tool implementations | `security_agents/tools/catalog.py` | implemented, tested |
| Worktree / test runner / check runner / patch applier | `security_agents/tools/services.py` | implemented, tested |
| `scope_guard` (pure) | `security_agents/scope_guard.py` | implemented, exhaustively tested |
| Sandbox: snapshots, diffs, local dev driver | `security_agents/sandbox/` | implemented, tested |
| Sandbox: hardened Docker driver | `security_agents/sandbox/driver.py` | implemented; **argv + reaper tested, execution UNVERIFIED** (no Docker engine on the dev machine; needs pinned images, INFRA-005) |
| Check templates v0 (ownership, bounds) | `security_agents/checks/library.py` | implemented, executed against the owned fixture |
| Orchestrator state machine + gates | `security_agents/workflow/` | implemented, tested |
| Contracts | `security_agents/contracts/` | **local V0 adapter**, pending `shared/` (CORE-001) |
| Code intelligence | `security_agents/intel/` | **local Python-AST adapter**, pending `code_intelligence.api` (INTEL-007) |
| LLM gateway | `security_agents/llm/` | consumer-side port + providers, pending the backend gateway (CORE-010) |

## Install and run

```bash
cd security-agents
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

Run the full assessment on the owned demo target (scripted model turns, real
sandboxed execution):

```bash
cd security-agents && .venv/bin/python -m security_agents.cli --target ../examples/payments-lite --auto-approve
```

Tests:

```bash
cd security-agents && .venv/bin/python -m pytest tests -q
```

Lint and types:

```bash
cd security-agents && .venv/bin/python -m ruff check security_agents tests
```

Opt-in live provider smoke (real Claude requests, costs money, needs an
authorized key):

```bash
cd security-agents && RUN_LIVE_LLM_EVAL=1 .venv/bin/python -m pytest tests/test_live_provider.py -v
```

The local sandbox driver is a **development** driver and not a security
boundary; it refuses to start unless `SANDBOX_ALLOW_LOCAL_PROCESS=1` is set (the
tests pass `allow=True` explicitly). Use the Docker driver for anything else, and
only with a digest-pinned image.

## Environment

| Variable | Meaning |
|---|---|
| `ANTHROPIC_MODEL` | default model id (falls back to `claude-opus-5-5`) |
| `AGENT_MODEL_OVERRIDES` | per-role override, JSON (`{"patch":"claude-opus-5-5"}`) or `scout=...,patch=...` |
| `ANTHROPIC_SERVER_FALLBACKS` | server-side refusal fallback mode; `off` disables |
| `RUN_LIVE_LLM_EVAL` | `1` enables the opt-in live tests |
| `SANDBOX_ALLOW_LOCAL_PROCESS` | `1` enables the dev driver |
| `SANDBOX_IMAGE` / `SANDBOX_TARGET_IMAGE` | digest-pinned sandbox images for the Docker driver |
| `SANDBOX_MAX_MEMORY_MB`, `SANDBOX_DEFAULT_TIMEOUT_SECONDS` | sandbox limits |

No secrets are ever placed in prompts, sandboxes or stored transcripts; the
sandbox environment is scrubbed and transcripts pass through the redactor.

## Public API

`security_agents.api` is the surface other subsystems import:

| Export | For |
|---|---|
| `run_assessment` / `Orchestrator` / `OrchestratorConfig` | backend worker hosting an assessment |
| `run_agent_step` | a worker that owns its own state and runs one step |
| `scope_check` / `ActionRequest` / `Decision` | backend scope API and any network-capable caller |
| `PatchWorktree`, `TestRunner` | **shared repair sandbox** for `code_review` (Sai) |
| `ALL_SPECS` | UI/metadata: role, version, budget, tools per agent |
| `CodeIntel` | the port `code_intelligence` should satisfy |

## How the agents are kept honest

- **Permissions are code.** `AGENT_TOOL_ALLOWLIST` is enforced by the registry
  before a handler runs; a spec cannot grant itself a tool the registry withholds.
- **Scope is checked twice.** Once at `SCOPE_CHECK`, again before every
  network-capable tool call, and the sandbox driver refuses a target network
  without an allowed decision.
- **Outcomes come from execution.** Probe's outcome is derived from the check
  template's `matches_expectation`; if the agent disagrees, the executed result
  wins and the disagreement is recorded. Verify's verdict is computed by
  `compute_verdict()` from executed records; the model only writes the summary.
- **Verify is structurally independent.** Its own `AgentRun`, a fresh checkout,
  fresh sandboxes, the diff artifact only, and no Patch transcript.
- **Model output carries no authority.** No output schema has a field that
  approves, verifies or widens scope (asserted by a test).
- **Citations are validated.** A hypothesis, cause span or recommendation citing
  a file or line range that is not in the pinned snapshot is dropped.

## Layout

```
security-agents/
  security_agents/
    api.py            # public surface
    cli.py            # run an assessment locally
    contracts/        # local V0 typed contracts (adapter)
    llm/              # gateway port, live/fake/replay providers
    runtime/          # AgentSpec + the agent loop
    agents/           # scout probe trace diagnose patch fortify verify
    tools/            # registry, catalog, execution services
    checks/           # reviewed check templates
    sandbox/          # workspace, drivers, in-sandbox entrypoint
    intel/            # code-intelligence port + local adapter
    workflow/         # state machine, gates, orchestrator
    scope_guard.py
    redact.py
  tests/
```

## Tasks

SEC-001 … SEC-013. Status and evidence: [coordination/status/ALAN.md](../coordination/status/ALAN.md).
