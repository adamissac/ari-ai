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
| Sandbox: hardened Docker driver | `security_agents/sandbox/driver.py` | implemented; **six real-container tests pass in CI** (digest-pinned base; isolation, timeout cleanup, fixture suite and checks) |
| Check templates v0 (ownership, bounds) | `security_agents/checks/library.py` | implemented, executed against the owned fixture |
| Orchestrator state machine + gates | `security_agents/workflow/` | implemented, tested; `external_pending` pauses for functional approvals |
| Host adapter | `security_agents/host_adapter.py` | implemented: finding lifecycle via `set_finding_status`, durable `save_checkpoint` / `claim_checkpoint` resume, Sai's functional repair + independent Verify |
| Contracts | `security_agents/contracts/` | local runtime adapters; host boundary exports canonical `shared/` contracts |
| Code intelligence | `security_agents/intel/` | hosted Git snapshots use the shared durable intelligence service; explicit dev fixtures use the local adapter |
| LLM gateway | `security_agents/llm/` | standalone providers plus hosted `host.llm()` gateway integration |
| Trained specialists | `security_agents/specialist_bridge.py` → `../specialists/` | one trained model per agent; advisory prompt data, Scout re-rank, Verify review note; audited `specialist.inference`; no authority ([ADR-0014](../docs/decisions/0014-trained-specialist-models.md)) |

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
| `ANTHROPIC_MODEL` | default model id (falls back to `claude-haiku-5-5`) |
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
- **Repository-declared tests are durable policy.** A root `build_recipe.json`
  may list `"protected_tests": ["tests/test_api.py"]`; only normalized paths
  under its `test_roots` (default `tests/`) are honored, and edits to them fail
  Verify's `no_test_tampering` check. Runner configuration changes fail that
  check too: any added, modified, deleted, or renamed `conftest.py`; byte
  changes to `pytest.ini` / `.pytest.ini` and `pytest.toml` / `.pytest.toml` at
  any depth; changes to the
  `[pytest]` section of `tox.ini`; changes to `[tool:pytest]` or
  `[options.entry_points].pytest11` in `setup.cfg`; and changes to
  `tool.pytest`, `project.entry-points.pytest11`, or
  `tool.poetry.plugins.pytest11` in `pyproject.toml`, including nested
  `pytest.ini`, `.pytest.ini`, `pytest.toml`, `.pytest.toml`, `tox.ini`,
  `setup.cfg`, and `pyproject.toml` files. Explicit `-c` /
  `--config-file` targets are byte-protected; a pinned `--rootdir` byte-protects
  only `pytest.ini`, `.pytest.ini`, `pytest.toml`, and `.pytest.toml` beneath
  that directory, while the same section-level checks apply to `tox.ini`,
  `setup.cfg`, and `pyproject.toml` there. Unreadable or invalid pinned pytest
  configuration fails closed with `SNAPSHOT_NOT_READY`. Plugin paths are
  protected from additions, edits, and deletions: module files, extension
  variants, package contents, and parent-package shadows are resolved from the
  repository root and pinned `pythonpath` entries. `-p` options in pinned
  configuration and the recipe test command are included. Dependency-only
  `pyproject.toml` edits and unrelated `tox.ini` / `setup.cfg` changes are
  allowed. Verify reads the test command from the pinned snapshot's
  `build_recipe.json`, not the patched copy. Top-level `pytest.py`, `pytest/`,
  `_pytest/`, `pluggy.py`, `pluggy/`, `py.py`, `py/`, `sitecustomize.py`, and
  `usercustomize.py` shadow paths, root `.pth` files, and modules
  named by pinned literal `pytest_plugins` declarations in conftests and Python
  files under test roots, `-p` addopts, or pytest11 entry points are also
  protected. Changed non-test-root Python files are checked for new or modified
  pytest hook definitions, hookimpl decorators, module-level `pytest_*`
  assignments, `_pytest` / pluggy imports including literal dynamic imports,
  and `pytest_plugins` assignments. Packaging settings in `setup.py` are not
  semantically inspected, but `setup.py` is covered by the changed-Python-file
  hook, import, and `pytest_plugins` scan.
- **Known limitation:** a pre-existing path under a recipe test root longer
  than 400 characters is rejected by `safe_rel_path`; Verify fails closed and
  rejects every patch for that repository. The longest tracked paths currently
  under this repository's `tests/` and `scripts/rehearsal/target-app/` are 40
  (`security/test_owasp_llm_agent_runtime.py`) and 17 (`build_recipe.json`)
  characters, respectively. This is a blocked fix, not a bypass.
- **Residual risk:** Verify's project suite runs with the test roots restored to
  the pinned snapshot, so patch-added test files cannot affect protected tests.
  Dynamic or nonliteral `pytest_plugins` declarations are recorded but are not
  statically expanded to arbitrary Python files. Obfuscated or dynamic
  registration through `globals()[...]`, `setattr(sys.modules[...], ...)`, or
  computed import names is not detected and remains within the broader risk
  that hostile patched application code executes in the suite; Verify does not
  protect against arbitrary hostile code in the patch.
  Unsupported or quoted diff path headers fail closed before patch application.
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

### Standards classifications

Producer standards fields resolve through the pinned offline `standards` catalog.
CWE proposals must identify real, nondeprecated weaknesses (categories such as
CWE-840 are not accepted as weakness classifications). CWE/CAPEC/ATT&CK catalog relationships are review candidates; they are not
automatically attached as ATT&CK mappings. These are
classifications, not evidence of production adversary activity.

Canonical `standards.mapping` validates classifications and reviewed rules.
Trace proposes the eight CVSS v3.1 base metrics, each citing a file span or the
executed validation run; uncited metrics are recorded as `unverified`. Code computes
the v3.1 vector, base score (FIRST specification with Roundup) and rating, and the
platform severity level comes from that rating (ADR-0012). This is a base score
only: it measures severity, not risk. Trace can also supply a complete set of CVSS
v4.0 base metrics backed by the executed run; that assessment is shown alongside as
provisional and never sets the level. Missing v4.0 metrics leave it unscored.

Scout's CWE must exist in the pinned MITRE catalog with mapping usage Allowed or
Allowed-with-Review; the OWASP API Security Top 10 2023 tag is derived in code from
a project mapping (`standards/standards/data/rules/cwe_owasp_api.json`), never by the
model. Trace steps may carry an ATT&CK Enterprise id and Diagnose and Fortify a
D3FEND id; each is validated against the pinned index, and "no applicable technique"
is an accepted answer.

### SARIF 2.1.0 export

`security_agents.standards.sarif.to_sarif` writes findings as a SARIF 2.1.0 log (one rule per CWE,
CVSS v3.1 base score in `security-severity`, OWASP API tag as a project mapping, ATT&CK and D3FEND in
result properties). The log is validated against the OASIS schema pinned in
`standards/standards/data/sarif-2.1.0.json` (OASIS Standard incorporating Approved Errata, 28 August
2023, notice included). The severity to SARIF level mapping is a project mapping.

### Rules of engagement

At SCOPE_CHECK the orchestrator issues a rules-of-engagement document aligned with
NIST SP 800-115 Appendix B (project mapping) from the approved scope. Every
scope-required tool call (Probe checks and Verify's re-check) is checked against it
after the scope guard: a missing, altered, stale, expired or non-matching RoE fails
closed with `SCOPE_DENIED` and a `tool.roe_denied` audit event. The host resume path
re-issues it from the reloaded scope.

```
cd security-agents
.venv/bin/python -m security_agents.standards.report   # offline table: standard, ids pinned, version, pass/fail, UNVERIFIED
.venv/bin/python -m security_agents.standards.smoke    # replay run; writes tagged finding JSON, RoE, SP 800-115 coverage and SARIF 2.1.0
```

D3FEND mappings use the owner-reviewed rules keyed by Fortify category and
confirmed check category. Unsupported combinations remain unmapped. Reviewed RL actions have simulation-derived D3FEND
classifications, while unsupported actions stay unmapped. No rule
executes a defensive action against real systems.

Model-proposed CVSS metrics are explicit provisional assumptions, even when they cite an executed run. A run identifier supplies provenance but does not prove an impact. Such scores list every assumption and require human review; missing metrics remain unscored. Incident closure requires actual regression artifact IDs/hashes; eradication requires a succeeded independent Verify run. All currently supported runtime sources are demo/replay/simulation, so correlated incidents retain simulated labeling even for executed demo logs.

Security Verify requires the same of Patch's added tests: the platform runs them on a
fresh unpatched checkout and they must fail there in a clean run, then pass after the
patch (`verify.clean_reproduction`, shared with the functional path; #248, #264).
Functional Verify requires nonempty generated regression tests that demonstrably
fail on the unpatched commit and pass after the candidate diff. Runner errors,
collection failures, timeouts, missing sandbox records and skipped generated tests
cannot establish a fix. Generated tests may not overwrite existing files. Human
approval resume reloads the current scope and worker host before execution.

## Retained regression sources

Accepted independent Verify can retain bounded test sources from its fresh workspace. Sources are captured before tests and compared afterward; unsafe, missing, symlinked, empty, changed or oversized sets produce no eligible archive. Host mode stores a redacted JSON archive with patch/verification/run IDs, checks and original source hashes, and attaches the returned artifact ID to hardening recommendations. Functional verification emits a deterministic policy-test retention recommendation. The archive associates source files with accepted verification; it does not claim every line or individual node ran. Incident evidence must use the stored artifact hash, since source redaction may change bytes.

## Docker execution evidence

[Security CI run 39033028814](https://github.com/adamissac/hackatl-agentic-security/actions/runs/39033028814)
on main commit `5b3ef50` built the sandbox image from its digest-pinned Python base
and executed `tests/test_docker_sandbox_live.py`: **6 passed**. The tests cover
non-root execution, read-only root filesystem, writable work/output mounts, kernel
network isolation, absence of host environment secrets, timeout removal, the owned
payments-lite suite, and ownership/bounds checks (including the protected lookalike).
The image tag is explicitly allowed only for this CI build; this evidence does not
provide a published image digest or a deployment attestation.

The same run's ordinary security suite passed **451 tests, with 18 skips**. These
scripted model runs and container tests do not establish a live seven-role provider
trace. Docker execution is CI evidence; no local Docker engine is claimed.


Scope guard policy follows ADR-0016: an owner-approved sandbox-only scope may have the same requester and approver, including in multi-member organizations. Empty or mixed/non-sandbox target sets do not receive the self-approval exception.
