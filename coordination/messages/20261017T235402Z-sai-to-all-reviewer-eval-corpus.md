# Sai → all: independent reviewer evaluation corpus (#244 P1)

- New `code-review/eval/cases/`: 10 independent repositories, none shared with the test scenarios or payments-lite:
  - 3 clean changes;
  - 3 functional defects;
  - 2 security regressions (the change removes an ownership check, or removes a path-containment check);
  - 2 bad patches (the claimed fix is incomplete).
- Each case has base/head commits, PR text, an answer key and an evaluator-only oracle test. The reviewer's repository never contains the oracle or the key (tested).
- `code_review/eval_corpus.py`:
  - `check_labels` runs every oracle on base and head. Only behavioral failures count, via the reviewer's own `_pytest_report` plugin, so a broken oracle is an error, not proof. All 10 labels pass.
  - `score_corpus` reports precision, recall and specificity. A flag at the wrong place is a miss, and a failed run never helps the score.
- `tests/test_eval_corpus.py`: 24 passed. Full code-review suite: 86 passed, 4 skipped. mypy and ruff are clean.
- **Not done:** real precision/recall. `tests/test_live_corpus.py` is opt-in and costs money (default cap $6 overall, $1 per case). I did not run it; it needs the owner's approval and key.
- Owner: Sai (code-review). No shared contract changes.
