# Reviewer model comparison — 2026-11-10

Live runs of `code-review/tests/test_live_corpus.py` (one review per case, real tools,
`anthropic_effort=high`), scored by `eval_corpus.score_corpus`. A defect counts only when a
validated finding or security hand-off cites the labeled root-cause function. Model set with
`ANTHROPIC_MODEL`; case set with `CODE_REVIEW_CORPUS_PREFIX`. Total spend: about $4.63.

## Original 10 cases: no difference

| Model | Runs | Defects located (of 7) | False positives (of 3 clean) | USD per run |
|---|---|---|---|---|
| claude-haiku-5-5 | 3 | 7, 6, 7 | 0, 0, 0 | 0.035 |
| claude-sonnet-5-5 | 1 | 7 | 0 | 0.39 |
| claude-opus-5-5 | 1 | 7 | 0 | 0.91 |

The one Haiku miss flagged `badpatch_refund_bound` at the wrong function. These cases are
single-file and nearly saturated, so they cannot separate the models.

## Hard cases (`hard_*`, 11 cases: 5 functional defects, 2 security regressions, 1 bad patch, 3 clean)

Each is a multi-file change whose defect needs a rule from the README plus code outside the
obvious hunk (a cache key, a refactored helper, a test edited to match the bug), or a clean
change that looks like a regression (an ownership check moved, a duplicate validation removed).
Every label is proven by its oracle (`uv run python -m code_review.eval_corpus`).

`FL` flagged and located, `F-` flagged at the wrong place, `--` not flagged.

| Case | haiku ×3 | sonnet ×2 | opus ×2 |
|---|---|---|---|
| hard_badpatch_dedupe_batches | -- FL -- | -- FL | FL -- |
| hard_clean_divmod_split | -- -- -- | -- -- | -- -- |
| hard_clean_owner_check_moved | F- F- F- | -- -- | -- -- |
| hard_clean_redundant_validation | -- -- -- | -- -- | -- -- |
| hard_defect_cache_key | FL FL FL | FL FL | FL FL |
| hard_defect_limit_after_debit | F- F- F- | FL FL | FL FL |
| hard_defect_refactor_safety_stock | FL FL FL | FL FL | FL FL |
| hard_defect_reschedule_self | FL FL FL | FL FL | FL FL |
| hard_defect_test_blessed | FL FL FL | FL FL | FL FL |
| hard_sec_default_action_role | FL FL FL | FL FL | FL FL |
| hard_sec_tenant_filter | F- F- F- | FL FL | FL FL |

| Model | Recall | Specificity | USD per 11 reviews |
|---|---|---|---|
| claude-haiku-5-5 | 0.625, 0.75, 0.625 | 0.667 each run | 0.043 |
| claude-sonnet-5-5 | 0.875, 1.0 | 1.0 | 0.47 |
| claude-opus-5-5 | 1.0, 0.875 | 1.0 | 1.08 |

## What the runs show

- Haiku raised a finding on the clean ownership refactor in 3 of 3 runs; Sonnet and Opus in 0 of 4.
- Haiku flagged `limit_after_debit` and `tenant_filter` every run but never at the labeled
  function; Sonnet and Opus located both every run. Which lines Haiku cited was not recorded.
- Sonnet and Opus scored the same; Opus cost about 2.3 times as much.
- All three missed `hard_badpatch_dedupe_batches` in about half their runs.

## Limits

- 11 cases, 2-3 runs per model. The three Haiku differences repeat in every run; the
  `dedupe_batches` result is noise at this sample size.
- Python only, small repositories. Nothing here measures the seven security agents.
- Production pins every agent to Haiku (`Settings.model_for`); no setting was changed.
