# MSG: V9 reporting isolated from frozen learning source
- From: Alan / Codex
- To: all
- Kind: status
- Timestamp (UTC): 2026-10-21T00:15:24.469951+00:00
- Branch: `feat/alan/v9-reporting`, based on29aa5f8, to be included in PR #376 after the cohort finishes
- Actual training checkout: `/private/tmp/rl-v8-continuation`, HEAD29aa5f8 unchanged.
- Work: portable read-only evidence verification, saved metrics/raw trajectory hash pins,
  secondary quiet/flagged-window thresholds, optional scientific figures and comparability
  guards for training budgets, source commit and reference checkpoint identities.
- Tests: targeted20 passed; earlier reporting/pipeline22 passed; Ruff lint/format pass.
  Synthetic reporting/figure fixtures only; no fresh held-out v9 policy execution.
- Next: finish all five fixed training runs; integrate reporting, derive saved-data
  diagnostics, hash-verify artifacts, publish all outcomes. No policy promotion.
