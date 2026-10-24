# Live Defense Phase 7A — deterministic first-responder orchestration

Status: **implemented** on `cursor/live-defense-first-responder-0044` from live
`origin/main`. This is the baseline future RL must beat. It is **not** a scanner
and **not** a simulator. AUTO-EXECUTE does not exist. Phase 7B is not started.

Codex owns RL research. This work does not train, promote, or edit v6 weights,
datasets, holdout sets, or the promotion registry.

## Architecture map (reuse, do not rebuild)

```
INGEST (existing)
  POST /ingest/runtime/{project}  → runtime_windows + MonitoringEvent
  job live_defense_shadow         → LivePolicyDecision { enforcement: NOT_EXECUTED }

FIRST RESPONDER (this phase; isolated job kinds)
  POST /projects/{id}/first-responder/mode   owner, audited
  job live_defense_first_responder           deterministic orchestrator 7a.1.1
      → FirstResponderDecision (versioned record, no invented probabilities)
      → FirstResponderInvocation (honest skip/queue; never fake success)
      → AnalystHandoff (delivered only after provider ack)
  job live_defense_agent_step                gated Scout/Trace/Diagnose/Fortify
                                             Probe iff AuthorizedScope
                                             Patch worktree-only, never deploy
                                             Verify independent of Patch

ENFORCEMENT (existing Phase 4; not started by first-responder)
  authorize.check → LiveControl → live_defense_execute
  OFF does not cancel these jobs or change their expiry/rollback/kill-switch
```

Reused: ConnectedApplication, ingest tokens, LivePolicyDecision, LiveControl
authorization gate, seven `AgentSpec`s in `security-agents/`, AuthorizedScope,
analyst review (still non-executing), existing Live Defense UI tabs.

Unchanged: Codex research, v6 checkpoints, holdout, `rl-defense/` training.

## Modes (server-enforced, fail closed)

| Intent | Effective (if app connected) | Jobs |
|---|---|---|
| `off` (default) | `off` | Cancel `live_defense_first_responder` + `live_defense_agent_step`. Do **not** cancel independently authorized control jobs. |
| `monitor` (alias `shadow`) | `monitor` | Investigate read-only agents when a trusted mapping exists; record; never Probe/Patch/Verify/execute. |
| `assisted_response` | `assisted_response` | Plus Probe (AuthorizedScope), Patch (worktree + human approval), Verify (independent), analyst handoff. Still never auto-execute. |
| `auto_execute` | rejected 400/422 | Does not exist. |

Org intent ≠ app effective permissions: a disconnected app is effective OFF
even if intent is ASSISTED RESPONSE. Kill-switch is **stop-enforcement**, not
**stop-monitoring**. Retention policy is unchanged on OFF.

## Orchestrator decisions

`ignore`, `record_observation`, `correlate`, `investigate`,
`confirm_with_probe`, `propose_worktree_patch`, `verify_independently`,
`recommend_control`, `escalate_to_analyst`, `defer_budget`, `cancel_run`,
`reject_auto_execute`.

Dedupe key `(project, app, window, source)`. Idempotent persist. Budgets and
deadlines fail closed. Loop prevention: one decision per window. Retry/backoff
via the existing job queue. LLM prose cannot set `confirmation=confirmed`.

## Seven-agent registry

Built from `security_agents.agents.ALL_SPECS` (real implementations).

| Agent | Class | Live integration in 7A |
|---|---|---|
| Scout, Diagnose, Fortify | investigative_readonly | Eligible in MONITOR/ASSISTED when mapping+snapshot exist; otherwise skipped honestly |
| Trace | investigative_readonly | Blocked until a confirmed Probe result exists |
| Probe | disruptive_scoped | ASSISTED + active AuthorizedScope only; no third-party hosts |
| Patch | code_changing | ASSISTED + human remediation approval; worktree only; silent deploy refused |
| Verify | disruptive_scoped | Independent of Patch; needs a PatchCandidate |

## Runtime ↔ code

Only with an owner-attested `DeployCommitMapping`. Else `correlation=UNKNOWN`.
Finding ids at a commit are listed as context, never as proof of this request.

## Analyst handoff

States: draft, queued, delivery_pending, delivered, delivery_failed,
acknowledged, investigating, confirmed, unverified, resolved, cancelled.
`delivered` requires provider confirmation. `confirmed` is distinct from
`unverified` and cannot be set from LLM prose.

## UI

Existing Live Defense shell gains a **First responder** tab with Observed /
Suspected / Verified / Recommended / Authorized / Executed / Failed / Rolled
back. Copy states that an RL recommendation is not executed defense.
