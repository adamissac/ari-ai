# Agent 2 — Probe (Red team)

Status: **specified**. Contract base: [AGENT_CONTRACT](AGENT_CONTRACT.md).

## Purpose
Validate or refute a single hypothesis with a **non-destructive** check executed
only against the authorized sandbox target, producing executed evidence.

## Responsibilities
- Choose a check template matching the hypothesis' `suggested_check_category`
  and the scope's `allowed_check_categories`.
- Fill the template's typed parameters (e.g. which fixture identities, which
  entry point) from the hypothesis and context.
- Run it through `checks.run_template` and interpret the structured result
  against the linked expectation.
- Report `confirmed`, `refuted`, or `inconclusive` with evidence.

## Not responsible for
Writing new attack logic, impact analysis, severity, fixes. Probe cannot author
arbitrary code; it can only parameterize reviewed templates.

## The check-template library (design)
- Location: `security-agents/checks/` (planned), versioned, code-reviewed with
  security-owner approval.
- Each template declares: `id@version`, category (e.g. `access_control.ownership`,
  `input_validation.bounds`), parameters schema, side-effect class (MVP:
  `read_only` only), expected evidence fields, and the expectation kinds it can
  judge.
- Templates operate on the target through its normal interfaces using synthetic
  fixture identities and data seeded into the target sandbox.
- Templates must be safe to run repeatedly and must not modify persistent state
  outside the ephemeral target.

## Input — `ProbeInput`
`hypothesis_id`, `scope_id`, `target_id`, context pack (`probe.hypothesis`, small),
fixture identity catalog for the target.

## Output — `ProbeOutput` → `ValidationResult`
`outcome`, `check_template_id@version`, `parameters`, `sandbox_run_id`,
`observations` (structured fields from the template result), `evidence[]`,
`interpretation` (≤ 500 chars, non-authoritative).

The outcome rule is deterministic where possible: templates return a
`matches_expectation: bool | null`; Probe's LLM may only explain, not override it.

## Tools & permissions
`code.read_span`, `expectations.for_subject`, `checks.list_templates`,
`checks.run_template`. Sandbox profile: `check-runner`. Network: `target-only`.
Write: `/out` only.

## Authorization & sandbox controls
- `scope_guard` on every `checks.run_template` call: scope active, target in
  scope, template category allowed.
- Per-step internal network with only the target attached; no egress.
- Limits per [15](../15_SECURITY_BOUNDARIES.md) §4; reaped on timeout.
- Every run audited with template id, params hash, scope id.

## Budget
Share of 20% across hypotheses; 3 min per hypothesis; ≤ 3 template runs per hypothesis.

## Handoff
→ Trace if `confirmed`; otherwise the hypothesis is closed as `refuted`/`inconclusive`
and remembered.

## Failure handling
Sandbox start failure → retry once → `inconclusive`. Scope denial → step failed,
no retry, audit.

## Success criteria / metrics
- Agreement with ground truth on fixtures (confirmed when planted, refuted when not).
- Zero out-of-scope network attempts (SB-01/SB-04 enforced).
- Reproducibility: re-running the same template + params yields the same outcome.
