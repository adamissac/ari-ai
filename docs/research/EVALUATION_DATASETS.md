# Evaluation datasets

Status: **specified**. How we measure whether findings and patches are right.

## Datasets

| Dataset | Content | Labels | Status |
|---|---|---|---|
| `examples/payments-lite` | Demo target with 1 planted functional bug, 1 planted authorization weakness | Expectations, planted findings, root-cause spans, reference fixes | Planned (DEMO-001) |
| `examples/fixtures/clean-*` | Small apps with **no** planted issues of the tested classes | Negative labels | Planned |
| `examples/fixtures/bad-patches/` | Patches that weaken tests, edit out of scope, or fix symptom only | Must be rejected by Verify | Planned |
| `tests/fixtures/llm/` | Recorded, redacted model responses per scenario | Expected structured outputs | Planned (TEST-001) |
| External labeled suites (OWASP Benchmark, SARD) | Analyzer test cases | Upstream labels | Research (TEST-101), license review needed |

All fixtures are written by us (or properly licensed), contain synthetic data
only, and are never deployed publicly.

## Labels schema (per fixture)

```
labels.yaml
  expectations: [{subject, statement, kind}]
  planted_findings: [{id, kind, weakness_class, subject, root_cause_span, expected_check_category}]
  reference_fixes: [{finding_id, diff_path}]
  negatives: [{subject, hypothesis_class}]   # must be refuted
```

## Metrics

| Component | Metric |
|---|---|
| Expectation extraction | Precision/recall vs labeled expectations; calibration by confidence level |
| Scout | Hypotheses → validated ratio; recall of planted findings |
| Probe | Agreement with labels (confirmed/refuted) |
| Review | Precision of validated functional findings |
| Diagnose | Root-cause span overlap with label |
| Patch/Verify | Accept rate; Verify rejects 100% of bad-patch fixtures; accepted patches pass held-out tests |
| End-to-end | Planted findings verified-fixed per run; false validated findings per run |

## Rules

- Never tune prompts on the same fixtures used to report results; keep a
  held-out fixture set once there are ≥ 3 fixtures.
- Report numbers only from committed scripts with fixture versions.
