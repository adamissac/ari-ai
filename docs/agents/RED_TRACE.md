# Agent 3 — Trace (Red team)

Status: **specified**. Contract base: [AGENT_CONTRACT](AGENT_CONTRACT.md).

## Purpose
For a confirmed weakness, describe what an attacker could reach and why it
matters, as an ordered attack path whose every step is labeled verified or
hypothesis, and assign severity with explicit factors.

## Responsibilities
- Use the call graph and data-sensitivity tags on expectations to determine
  reachable data/operations from the affected entry point.
- Build `AttackPath.steps`; mark a step `verified` only if a ValidationResult or
  test run evidences it.
- Compute `SeverityAssessment` with the rubric (reachability, privileges
  required, data sensitivity, verified path length). The level is computed by a
  deterministic function from factors; the LLM proposes factor values with
  citations.

## Not responsible for
Running new checks (it may *recommend* additional validation as a follow-up item),
fixes.

## Input — `TraceInput`
`finding_id`, `validation_result_id`, context pack (`trace.impact`), expectations
with data sensitivity.

## Output — `TraceOutput`
`attack_path: AttackPath`, `severity: SeverityAssessment`,
`followup_validation_suggestions: [str]` (informational; not auto-executed).

## Tools & permissions
`code.read_span`, `code.search`, `graph.*`, `expectations.for_subject`,
`findings.history`. No sandbox, no network, no writes.

## Authorization & sandbox controls
Not applicable (no execution). Output cannot trigger execution.

## Budget
10%; 3 min; ≤ 25 tool calls.

## Handoff
→ Diagnose with AttackPath + severity.

## Success criteria / metrics
- 100% of steps labeled; 0 steps marked verified without evidence (enforced).
- Severity agreement with human labels on fixtures (target ±1 level).
