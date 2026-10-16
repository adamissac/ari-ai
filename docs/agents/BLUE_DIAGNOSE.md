# Agent 4 — Diagnose (Blue team)

Status: **specified**. Contract base: [AGENT_CONTRACT](AGENT_CONTRACT.md).

## Purpose
Identify the root cause of a validated finding relative to intended behavior and
produce a remediation plan a reviewer can approve.

## Responsibilities
- Locate cause spans (where the expectation is violated, not just where the
  symptom appears), e.g. a missing ownership condition in a data-access function
  shared by several routes.
- Classify the cause (`missing_check`, `wrong_check`, `unsafe_default`,
  `logic_error`, `dependency`, `configuration`).
- Produce `RemediationPlan`: strategy, constraints (must keep confirmed
  expectations), files expected to change, test plan (which tests must fail
  before and pass after).
- Note other call sites sharing the root cause.

## Not responsible for
Writing the patch, approving remediation.

## Input — `DiagnoseInput`
`finding_id`, AttackPath, ValidationResult evidence, context pack
(`diagnose.root_cause`), related expectations and functional findings.

## Output — `DiagnoseOutput`
`root_cause: RootCause`, `plan: RemediationPlan`, `related_sites: [EvidenceRef]`.

Validation: `files_expected` must exist in snapshot (or be new test files);
`violated_expectation_ids` must exist.

## Tools & permissions
`code.read_span`, `code.search`, `graph.*`, `expectations.for_subject`,
`findings.history`, `static.analyze`. Read-only; may read Probe evidence. No
sandbox, no network.

## Authorization & controls
Output goes to a **human remediation approval** gate. Approval UI shows the plan,
files expected and test plan.

## Budget
10%; 3 min.

## Handoff
→ Patch after approval; if declined, finding stays `diagnosed`.

## Success criteria / metrics
- Root-cause location matches human label on fixtures.
- Plans approved without edits (user signal).
