# Verification scope

Unit fixtures exercise strict availability cutoffs, context/version binding, unknown
semantics, expired/revoked scopes, masked proposals, result schema consistency and
separation of recommendations from execution. Static inventory pins all seven source
implementations and can be verified against committed bytes without importing agents.
These are software invariant checks, not measured live incident outcomes.

No provider call, first-responder incident rollout, formal collection, training,
checkpoint load/promotion or customer enforcement is needed for these checks.
Repository CI may run its existing historical RL smoke suite; that is software
regression verification, not an authorized first-responder learning experiment.
Final executed check counts are recorded in the PR and session handoff. Source
inventory commit is intentionally the audit source, not the eventual documentation
merge commit. Historical evidence and frozen v6 registry identities remain unchanged.

Local checks at source 82b13a54: 242 selected research regressions passed in 26.50s,
including 23 first-responder fixtures; 91 shared tests passed in 1.13s; scoped Ruff
and strict adapter mypy passed; 594 Markdown files had zero broken links. Initial
PR CI found formatting in newly added tests; corrected without changing semantics.
Frozen v6 registry SHA-256 remains
c345593354856c50559ba16611853a0e4936a7efc11fa5704c224d3189271408.
