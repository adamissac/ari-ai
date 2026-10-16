# Agent 1 — Scout (Red team)

Status: **specified**. Contract base: [AGENT_CONTRACT](AGENT_CONTRACT.md).

## Purpose
Survey the attack surface of a snapshot and produce a ranked list of
evidence-backed **hypotheses** about weaknesses, each tied to intended behavior.

## Responsibilities
- Enumerate entry points and their auth dependencies from code intelligence.
- Compare entry points to behavioral expectations and to sibling conventions
  (e.g. an endpoint missing an auth dependency its siblings have).
- Run read-only static analysis and interpret results in context.
- Produce hypotheses with weakness class (CWE id), rationale, cited spans,
  linked expectations, confidence and a suggested **check category**.
- Skip hypotheses previously refuted for unchanged code.

## Not responsible for
Executing anything, contacting any target, judging exploitability, severity.

## Input — `ScoutInput`
`assessment_id`, `snapshot_id`, `entry_point_ids` (all or targeted), context pack
(`scout.surface`), expectation IDs, prior refuted hypothesis keys, max hypotheses.

## Output — `ScoutOutput`
`hypotheses: [Hypothesis]` (≤ cap), `coverage: {entry_points_reviewed, skipped_with_reason}`,
`signals: [suspicious_instruction?]`.

Validation rules: each hypothesis has ≥ 1 cited span that exists in the snapshot;
`suggested_check_category` must exist in the template library; confidence ∈ enum.

## Tools & permissions
`code.read_span`, `code.search`, `graph.*`, `expectations.for_subject`,
`findings.history`, `static.analyze`. Network: none. Sandbox: none. Write: none.

## Authorization & sandbox controls
None required to run (no execution, no network) beyond the assessment's
`SCOPE_CHECK`. Scout's output cannot trigger execution; the orchestrator decides
which hypotheses go to Probe.

## Budget
20% of assessment tokens; 5 min; ≤ 40 tool calls.

## Handoff
→ Probe: one hypothesis per Probe step, ranked by `confidence × expectation
criticality`, capped (default 10).

## Failure handling
Invalid output → retry once → step failed → assessment continues to reporting
with "security recon failed" noted.

## Success criteria / metrics
- Precision: validated ÷ hypotheses sent to Probe (target ≥ 30% on fixtures).
- Recall on planted weaknesses in `examples/` (target: finds the planted
  authorization weakness in `payments-lite`).
- Citation validity: 100% (enforced).
