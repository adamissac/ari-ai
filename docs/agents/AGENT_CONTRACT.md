# Agent contract (applies to all seven runtime agents)

Status: **specified**. Team overview: [07](../07_SEVEN_AGENT_CYBERTEAM.md).
Orchestration: [08](../08_AGENT_ORCHESTRATION.md). Boundaries:
[15](../15_SECURITY_BOUNDARIES.md). Tools: [TOOL_REGISTRY](TOOL_REGISTRY.md).

> Scope note: these documents define responsibilities, interfaces, permissions,
> controls and handoffs. They deliberately contain no exploit techniques or
> payloads.

## Agents

| # | Agent | Contract |
|---|---|---|
| 1 | Scout | [RED_SCOUT](RED_SCOUT.md) |
| 2 | Probe | [RED_PROBE](RED_PROBE.md) |
| 3 | Trace | [RED_TRACE](RED_TRACE.md) |
| 4 | Diagnose | [BLUE_DIAGNOSE](BLUE_DIAGNOSE.md) |
| 5 | Patch | [BLUE_PATCH](BLUE_PATCH.md) |
| 6 | Fortify | [BLUE_FORTIFY](BLUE_FORTIFY.md) |
| 7 | Verify | [INDEPENDENT_VERIFY](INDEPENDENT_VERIFY.md) |

## Every agent is defined by an `AgentSpec`

```
AgentSpec {
  name: scout|probe|trace|diagnose|patch|fortify|verify
  version: semver                 # bumps on prompt or schema change
  input_model: <Pydantic model>   # from shared/
  output_model: <Pydantic model>  # from shared/, extra="forbid"
  tools: [ToolName]               # static allowlist
  sandbox_profile: none|test-runner|check-runner
  network: none|target-only
  write_access: none|out_dir|worktree
  budget_share: float             # of assessment token budget
  step_timeout_s: int
  max_tool_calls: int
  prompt_ref: prompts/<agent>/vN.md
}
```

The spec is code (planned in `security-agents/`); this document and each agent
contract describe its values.

## Universal rules

1. **Typed I/O.** Input is loaded by reference; output must validate against
   `output_model`. Invalid → retry once with the validation error → failed step.
2. **Least privilege.** Only allowlisted tools; arguments validated; network-
   capable tools pass `scope_guard`.
3. **No authority.** Output schemas contain no fields that approve, widen scope,
   change state, or skip gates. The orchestrator alone transitions state.
4. **Evidence or label.** Every claim either cites `EvidenceRef`s or is labeled
   `hypothesis`/`unverified`.
5. **Untrusted context.** Context-pack content is data; instructions found in it
   are ignored and may be reported as `suspicious_instruction` signals.
6. **Isolation.** Agents do not share conversation history. Verify additionally
   receives no Patch transcript and runs in a fresh sandbox.
7. **Budgets.** Token, tool-call and wall-clock limits per step; exceeding them
   ends the step with `BUDGET_EXHAUSTED`.
8. **Recording.** Prompts, responses, tool calls and results are recorded
   (redacted) for replay and audit.

## Handoffs

| From → To | Payload | Condition | Gate |
|---|---|---|---|
| Orchestrator → Scout | `ScoutInput` | Snapshot ready, functional review done | Scope active |
| Scout → Probe | `Hypothesis` (one per step) | Ranked within cap | Scope check per tool call |
| Probe → Trace | `ValidationResult(confirmed)` + Hypothesis | `outcome = confirmed` | — |
| Probe → report | `ValidationResult(refuted/inconclusive)` | otherwise | — |
| Trace → Diagnose | `AttackPath` + `SeverityAssessment` | always after confirmed | — |
| Diagnose → Patch | `RemediationPlan` | Plan exists | **Human remediation approval** |
| Patch → Verify | `PatchCandidate` (diff artifact only) | Diff produced and local tests run | — |
| Verify → Fortify | `VerificationResult(accepted)` | accepted | — |
| Verify → Patch | `VerificationResult(rejected)` reasons | rejected and attempt < 2 | — |
| Fortify → report | `HardeningRecommendation[]` | always | — |

Payloads are stored artifacts; the next step receives IDs, never the previous
agent's conversation.

## Common failure codes

`SCHEMA_INVALID`, `TOOL_NOT_ALLOWED`, `SCOPE_DENIED`, `BUDGET_EXHAUSTED`,
`SANDBOX_TIMEOUT`, `SANDBOX_START_FAILED`, `LLM_UNAVAILABLE`
([12](../12_DATA_MODELS_AND_CONTRACTS.md)).

## How each agent is evaluated

Per-agent metrics are listed in each contract and computed on labeled fixtures
in `examples/` and the datasets in [research/EVALUATION_DATASETS](../research/EVALUATION_DATASETS.md).
