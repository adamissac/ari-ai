# MSG: V9 preregistered five-seed quiet-validation study
- From: Alan / Codex
- To: all
- Kind: status
- Timestamp (UTC): 2026-10-20T22:46:43Z
- Branch: `feat/alan/live-retrain-v9`, stacked on PR #375
- Owner request: explicitly continue with preregistration and fresh holdout.
- Plan: train_v8 unchanged; val_v9 adds quiet delegate/outsider regimes; fresh holdout_v9
  uses unused names and seeds. All five training seeds0–4,150k steps each,100 episodes
  per held-out scenario. Real registered incumbent v6 is gate comparator, read-only.
- Evidence before launch: env/split/pipeline smoke31 passed; aggregation/split9 passed;
  Ruff lint and format pass. No holdout_v9 episode has executed.
- Protocol discrepancy surfaced: docs/17 fixes simulator metrics; historical lab runs
  used a different environment and one seed. ADR-0018 proposes explicit five-seed lab
  extension; v9 claims experimental lab evidence only, no simulator TTC/transfer claim.
- Action: review preregistration/instrumentation; no automatic policy promotion. All
  failure cases and seeds retained; no best-seed selection or implicit failed-seed rerun.
