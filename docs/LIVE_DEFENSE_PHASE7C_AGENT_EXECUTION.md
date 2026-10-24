# Live Defense Phase 7C — live authorized agent execution

Status: **implemented** on `feat/alan/live-defense-phase7c-agent-execution` from live
`origin/main` (PR #439 / Phase 7A merged). This is **not** Codex Phase 7B RL
research, **not** RL training, **not** AUTO-EXECUTE, and **not** customer
production enforcement.

**Verdict for one company-owned staging app: ENGINEERING GO FOR AUTHORIZED
INVESTIGATIVE EXECUTION.** Leave the PR open for explicit security review of
the execution trust-boundary expansion (the first-responder now runs real
Scout/Diagnose agent loops). Do not merge from this agent.

## Return fields

| Item | Status |
|---|---|
| Branch | `feat/alan/live-defense-phase7c-agent-execution` |
| Modes | OFF / MONITOR\|SHADOW / ASSISTED RESPONSE; AUTO-EXECUTE rejected; fail closed |
| What executed for real | Scout and Diagnose run `security_agents.runtime.run_agent` against an owner-attested mapped snapshot when FakeLLM (tests/e2e) or a live Anthropic key is present |
| Skipped / gated | Probe is not expanded (AuthorizedScope eligibility stays `completed_unverified`, `provider_mode=none`). Patch worktree-only, never deployed. Verify eligibility is not verification. Trace waits for confirmed Probe. Fortify waits for independently executed `verification_results` |
| Confirmation | Always `unverified`. `executed` on the decision stays `false` (no LiveControl). `predicted_probability` stays null |
| Schema | **0.22.0** additive. Open PR #412 keeps **0.20.0**. Alembic stays **0015** (execution lives in existing invocation JSONB) |
| Orchestrator | `7c.1.0` |
| RL | Decision-time records include genuine cost/latency/tools/transcript. **Do not train** |

## Architecture (reuse Phase 7A)

```
INGEST (existing)
  POST /ingest/runtime/{project}  → runtime_windows + MonitoringEvent
  job live_defense_shadow         → LivePolicyDecision { enforcement: NOT_EXECUTED }

FIRST RESPONDER (Phase 7A decide + Phase 7C execute)
  POST /projects/{id}/first-responder/mode   owner, audited
  job live_defense_first_responder           deterministic orchestrator 7c.1.0
      → FirstResponderDecision (versioned; predicted_probability=null; executed=false)
      → FirstResponderInvocation
      → AnalystHandoff (delivered only after provider ack)
  job live_defense_agent_step
      Scout   — real agent loop when mapping+snapshot exist
      Diagnose — real agent loop after Scout hypotheses
      Fortify — skipped_no_prerequisite without verification_results
      Trace   — skipped_no_prerequisite until confirmed Probe
      Probe   — not expanded; scope eligibility ≠ execution
      Patch   — worktree-only; silent deploy refused
      Verify  — eligibility is not verification

ENFORCEMENT (existing Phase 4; not started by first-responder)
  authorize.check → LiveControl → live_defense_execute
  OFF does not cancel these jobs
```

LLM calls run **outside** the first-responder advisory lock. Artifacts persist
in short transactions. OFF / cancel is re-checked before the loop and before
writing the invocation. A running loop sees `cancelled()` / `kill_switch`.

## What executed vs skipped

| Agent | Phase 7C path | Confirmation |
|---|---|---|
| Scout | `run_agent` + `scout.to_hypotheses` when mapping and snapshot exist | unverified; integrity `checked` means cited snapshot spans, not a confirmed threat |
| Diagnose | `run_agent` after Scout hypotheses; input is labelled a hypothesis | unverified |
| Fortify | `skipped_no_prerequisite` | n/a |
| Trace | `skipped_no_prerequisite` (orchestrator still blocks until confirmed Probe) | n/a |
| Probe | `completed_unverified` if AuthorizedScope else `skipped_no_scope`; no probe loop | unverified |
| Patch | skipped / blocked; `worktree_only=true`; `silent_deploy=false` | n/a |
| Verify | `completed_unverified` without independently executed `verification_results` | unverified |

Missing LLM key → invocation `failed` with `error_code=LLM_UNAVAILABLE`, not a
faked success. Missing snapshot → honest `skipped_no_snapshot`.

## Control boundaries (unchanged)

- No AUTO-EXECUTE route.
- OFF cancels first-responder jobs only. Advisory lock serializes mode writes with dispatch.
- Owner-only mode writes. Outsiders 404; members 403.
- Org intent ≠ app effective permissions.
- Probe is not silently expanded. Patch is not silently expanded.
- LLM prose cannot confirm a threat.
- `evidence_state=verified` still requires independently executed `verification_results`.

## Schema vs open #412

| Branch | SCHEMA_VERSION | Alembic |
|---|---|---|
| main after #439 | 0.21.0 | 0015 |
| this PR (Phase 7C) | **0.22.0** additive | **0015** (no 0016) |
| open #412 | 0.20.0 reserved | none |

#412 must rebase to **0.23.0** (or later unused) if it lands after this PR, not
overwrite 0.22.0. This PR does not claim 0.20.0.

## RL-data readiness

`FirstResponderInvocation.execution` (`AgentExecutionRecord`) records
`provider_mode`, `model_id`, `cost_usd`, `latency_ms`, `llm_turns`,
`tool_call_count`, transcript and output artifact ids, `execution_integrity`,
and `error_code`. `predicted_probability` is always null.
`evidence_verified` is always false. **Do not train.**

## Next

Human/security review of this PR. Do not merge from the implementing agent.
Do not enable autonomous containment, production controls, or unrestricted
probing. Live Anthropic Scout/Diagnose remains opt-in (issue #10).
