# MSG: v8 continuation — gate against the incumbent, preserve historical evidence
- From: Alan / Codex
- To: Adam, all
- Kind: handoff
- Timestamp (UTC): 2026-10-20T22:35:00Z
- Branch: `feat/alan/rl-v8-continuation` (base `45f71eca`)
- Related: PR #370 inline review; issue #317
- Summary: v8's saved recommend_promote compares with a simulator baseline, not incumbent
  v6. Added promotion baseline binding, report hash pins, nonempty passing checks,
  `online --registry PATH`, and reference-alias validation. Historical evidence unchanged;
  no holdout rerun, new training experiment or promotion.
- Evidence: focused pytest (`test_live_retrain`, `test_live_v6`, `test_live_v8`,
  `test_v8_evidence`) 35 passed; final evidence/registry-backed pipeline regressions
  (`test_v6_evidence`, `test_v8_evidence`, v8 pipeline smoke) 15 passed.
  Ruff lint and Python format checks pass. Full RL suite result to follow in PR.
- Migration: old registry entries without report_sha256 require explicit re-registration.
  Reports against a different deployed checkpoint need a fresh preregistered evaluation.
- Action: review safety changes before merge. Keep issue #317 open for authenticated
  approvals, report signatures/full schema validation and concurrency. Next training
  research: quiet validation coverage, fresh holdout, actual incumbent baseline.
