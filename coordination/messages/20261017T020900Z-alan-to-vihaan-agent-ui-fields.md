# MSG: what the seven agents actually emit, for the assessment UI
- ID: `20261017T020900Z-alan-to-vihaan-agent-ui-fields`
- From: alan
- To: vihaan
- Kind: `integration`
- Timestamp (UTC): 2026-10-17T02:09:00Z
- Branch / commit / PR or issue link: `feat/alan/seven-agent-runtime` @ `b0ae682`
- Related subsystem(s): `frontend/`, `security-agents/`, `backend/`

## Summary (facts, not assumptions)

The seven agents now produce real records, so here is what you can render and —
more importantly — what each field means, so the UI does not overstate it. All
types are the canonical ones from `shared/generated/ts/contracts.ts`; the
transport is Srihith's SSE and REST.

## Per-agent record, in the order a run produces them

| Step | Record you get | Row label | Evidence to link |
|---|---|---|---|
| Scout | `Finding(status=hypothesis)` + `Hypothesis` | `Hypothesis.rationale` (first line is the title until Srihith adds `Hypothesis.title`) | `cited_spans[]` → file + line range at `commit_sha` |
| Probe | `ValidationResult` | `outcome`: confirmed / refuted / inconclusive | `sandbox_run_id`, `check_template_id@version` |
| Trace | `AttackPath` + `SeverityAssessment` | severity `level` | each `PathStep.verified` + its `evidence[]` |
| Diagnose | `RootCause` + `RemediationPlan` | `cause_class` | `cause_spans[]`; plan `files_expected` |
| Patch | `PatchCandidate` | `files_changed`, `attempt` | `diff_artifact_id` (fetch the diff artifact) |
| Verify | `VerificationResult` | `verdict` | `checks[]` (5 named checks) + `sandbox_run_ids` |
| Fortify | `HardeningRecommendation[]` | `category`, `effort` | `references[]` |

Every step is also an `AgentRun` with `agent`, `step_key`, `attempt`,
`provider_mode`, `model_id`, `usage` and `tool_calls[]`.

## Four things the UI must not get wrong

1. **`hypothesis` is not a finding.** docs/07 is explicit: only `validated` and
   later statuses may be shown as findings; hypotheses belong in a separate,
   clearly labelled list. A confirmed finding is one where
   `ValidationResult.outcome == "confirmed"`, which means a check actually ran.

2. **`provider_mode` decides what you may claim.** `AgentRun.provider_mode` is
   `live`, `replay` or `fake`. Anything that is not `live` is a scripted or
   recorded run and the UI should say so on the step (a small "replay" chip is
   enough). The demo will contain both, and a reviewer must be able to tell them
   apart at a glance. Same spirit as Adam's `simulation_derived` on RL
   recommendations.

3. **`PathStep.verified` is load-bearing.** `true` means executed evidence backs
   that step (a check run or a test run); `false` means it is reasoning. The
   platform enforces this — a step claiming `verified` without a matching
   sandbox run is downgraded before it is stored — so please render the two
   differently (solid vs dashed, or a "hypothesis" tag) rather than showing one
   list of steps.

4. **Verify's verdict is computed, not written.** `VerificationResult.verdict`
   comes from the five `checks[]`; `summary` is model prose and is explicitly
   non-authoritative. If you show the summary, show the check table next to it.
   `accepted` requires all five to pass — `shared` rejects anything else, so you
   can trust it.

## Things worth showing that are easy to miss

- **A refused tool call is a feature, not an error.** `ToolCallRecord.outcome`
  can be `denied` with `error_code: TOOL_NOT_ALLOWED` or `SCOPE_DENIED`. That is
  the permission system working (an agent asked for something it may not have).
  A neutral "refused by policy" style beats a red error.
- **`sandbox_run_id` + `isolation_level`.** My sandbox results carry
  `isolation_level`, and the local development driver reports
  `process-dev:not-a-security-boundary`. If that value reaches you, it should be
  visible — it means the run was not containerised.
- **Severity factors.** `SeverityAssessment.factors` (reachability, privileges
  required, data sensitivity, verified path) are the inputs the level is computed
  from; showing them makes the number defensible.
- **Attempts.** `PatchCandidate.attempt` is 1 or 2, and a rejected attempt 1
  followed by an accepted attempt 2 is a story worth rendering as a timeline.
  `VerificationResult.reasons[]` are the machine reasons that drove the retry.

## Interface requested/proposed

Nothing from you. Two requests to Srihith that affect your rendering, so you may
want to add your voice on issue #9: `Hypothesis.title` (so you get a real row
label instead of a truncated rationale), and `RemediationPlan.test_plan_detail`
split into must-fail-before / must-pass-after (so the approval screen can show
what the fix is expected to change). Details in
`coordination/messages/20261017T020600Z-alan-to-srihith-contracts-v0-ack.md`.

## Breaking change? migration/test impact

None.

## Action required by recipient

1. Tell me if any field you need for the timeline is missing from the table
   above — easier for me to add now than after M3.
2. If you want a fixture to build against before the backend is wired up, run
   the CLI and point your mock at the JSON:
   `cd security-agents && .venv/bin/python -m security_agents.cli --target ../examples/payments-lite --auto-approve --report /tmp/assessment.json`
   That file contains the full state sequence, every agent run with usage, and
   the finding with its verdicts. It is labelled `provider_modes: ["fake"]`, so
   please keep that label visible in any screenshot taken from it.

## Response-by milestone

Before M6 (frontend shows real assessments).

## Evidence: command output, test status, logs or exact file paths

```
cd security-agents && .venv/bin/python -m pytest tests -q
325 passed, 3 skipped in 88.51s
```
- host mirroring (what reaches the backend): `security-agents/security_agents/host_adapter.py`
- canonical mapping per record: `security-agents/security_agents/contracts/export.py`
- the five verification checks: `security-agents/security_agents/agents/verify.py`
