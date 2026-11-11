# Seven-agent model comparison — 2026-11-10

Live runs of the standalone orchestrator on the two labeled example targets, all seven agents
on one model per run, remediation auto-approved (local fixtures only):

```
cd security-agents
ANTHROPIC_MODEL=<model> uv run python -m security_agents.cli --target ../examples/<target> \
  --mode live --i-have-authorization --auto-approve --max-hypotheses 4 --validate 4 \
  --max-usd <cap> --report <file>
```

Base: `main` @ `9fe191ec`. Local process sandbox. Total spend: about $1.20.

## Results

"Planted" is the answer key in each target's `labels.yaml`. A planted defect counts when its
finding reached `hardened` (confirmed by an executed check, fix accepted by Verify, Fortify ran).

| Target | Model | Runs | Planted defects hardened | Other findings | USD per run | Wall time |
|---|---|---|---|---|---|---|
| payments-lite (2 planted) | claude-haiku-5-5 | 2 | 2, 2 | none | 0.065, 0.058 | 152 s, 112 s |
| payments-lite | claude-sonnet-5-5 | 1 | 2 | none | 0.64 | 88 s |
| inventory-lite (1 planted) | claude-haiku-5-5 | 2 | 1, 1 | 1 inconclusive each | 0.035, 0.035 | 83 s, 75 s |
| inventory-lite | claude-sonnet-5-5 | 1 | 1 | 1 inconclusive | 0.37 | 58 s |

- Every run completed with no failed agent step.
- No run confirmed a labeled negative (a route that is correct).
- The extra inventory-lite finding in every run is a concurrency suspicion on `POST /transfers`
  that the executed check did not confirm; the answer key says that route is correct.
- Sonnet cost about 10 times as much and finished sooner.

## What this shows

Haiku already completes the whole loop on both targets, so they cannot separate the models.
Opus 5.5 was not run: it could only tie, at a higher price.

## Limits

- Two small Python services with three planted defects in total; 1-2 runs per model.
- Expectations are read from each target's `labels.yaml`, the same for every model.
- Nothing here measures harder cases: multi-file defects, write routes, misleading changes. The
  reviewer needed such cases before its models separated
  (`code-review/eval/REVIEWER_MODEL_COMPARISON_2026-11-10.md`, #894).
- No production setting was changed. ADR-0015 (Haiku for the seven agents) stands.
