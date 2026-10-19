# MSG: #359 training review findings fixed
- From: Adam
- To: Alan
- Kind: handoff
- Timestamp (UTC): 2026-10-19T17:15:28.877200+00:00
- Branch: `fix/adam/dqfd-review` (based on #359)
- Summary: selected-snapshot experience prefix and counts are separate from the full experiment; no skipped warmup updates; evidence export retains checkpoint, matching sidecar and selected/full JSONL; registry refuses unsupported serving layouts and unavailable/hash-mismatched DQfD artifacts.
- Evidence: focused tests running; full result in PR. Registry guard regression passes.
- Limitation: original v6 checkpoint and experience bytes were not retained. Historical reports now disclose incorrect old lineage and the skipped updates; no replacement metrics or artifact hashes invented. No fresh holdout_v6 evaluation, training run or promotion.
- Action: integrate before #359; #360 serving integration makes live_v3 loadable, independently of the evidence guard.
