# Agent 6 — Fortify (Blue team)

Status: **specified**. Contract base: [AGENT_CONTRACT](AGENT_CONTRACT.md).

## Purpose
Turn a verified fix into lasting prevention: regression tests, hardening
recommendations, and inputs for monitoring and RL.

## Responsibilities
- Promote the finding's validating tests into `RegressionTest` records linked to
  affected symbols (so monitoring re-runs them on changes).
- Recommend class-level hardening (e.g. centralize ownership checks in one
  dependency, add a lint rule, add a policy test for all routes of a router).
- Identify sibling sites with the same pattern (from Diagnose's related sites)
  and propose them as new hypotheses for a future run (not executed now).
- Provide monitoring hints: which entry points/signals to watch.

## Not responsible for
Applying changes; recommendations are artifacts for humans.

## Input — `FortifyInput`
`finding_id`, `verification_result_id`, RootCause, related sites, context pack.

## Output — `FortifyOutput`
`regression_tests: [RegressionTest]`, `recommendations: [HardeningRecommendation]`,
`future_hypotheses: [HypothesisDraft]`, `monitoring_hints: [EntryPointRef]`.

## Tools & permissions
Read-only code/graph/expectation/findings tools, `static.analyze`. No sandbox,
no network, no writes (proposed tests stored as artifacts by the platform).

## Authorization & controls
None beyond assessment scope; nothing is executed or applied.

## Budget
10%; 3 min.

## Handoff
→ report; regression tests → intelligence layer; monitoring hints → monitoring
policy.

## Success criteria / metrics
- Every verified finding has ≥ 1 regression test (enforced).
- Recommendation acceptance rate (user signal).
