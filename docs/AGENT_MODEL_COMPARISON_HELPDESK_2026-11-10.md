# Seven-agent model comparison on helpdesk-lite — 2026-11-10

`examples/helpdesk-lite` was built for this comparison: eleven modules, four planted weaknesses
(CWE-639, CWE-306, CWE-89, CWE-22) that each need a second file to see, and a correct lookalike
beside each. Every planted defect is confirmed, and every lookalike cleared, by the platform's
own reviewed check templates run against the recipe (and by `label_checks/`).

```
cd security-agents
ANTHROPIC_MODEL=<model> uv run python -m security_agents.cli --target ../examples/helpdesk-lite \
  --mode live --i-have-authorization --auto-approve --max-hypotheses 8 --validate 8 \
  --max-usd <cap> --max-tokens 6000000 --report <file>
```

Standalone orchestrator, local process sandbox, all seven agents on one model per run.

## Results (final target)

| Model | Runs | Planted defects hardened (of 4) | Lookalikes confirmed (of 5) | USD per run | Wall time |
|---|---|---|---|---|---|
| claude-haiku-5-5 | 2 | 4, 4 | 0, 0 | 0.15, 0.13 | 229 s, 203 s |
| claude-sonnet-5-5 | 1 | 4 | 0 | 1.42 | 156 s |

- One Haiku run also raised a missing-authentication hypothesis on the help routes; the
  executed check refuted it.
- Sonnet cost about 10 times as much and finished sooner.

The harder target still does not separate the models. Scout on Haiku found all four defects in
every run, and the executed checks removed its one wrong hypothesis. ADR-0015 (Haiku for the
seven agents) stands on this evidence. Opus 5.5 was not run.

## Earlier runs on a first version of the target

The first version's unauthenticated route returned ticket counts across organizations, and the
target's own test asserted that count. Fixing the leak properly meant changing that test, which
Patch may not do. Those runs are not a model comparison, but they showed platform behavior:

- Sonnet scoped the report to the caller's organization; Verify rejected all four attempts
  because the existing test then failed. The finding ended `patch_rejected`.
- Haiku made the same fix once (rejected), then fell back to adding only the sign-in dependency
  (accepted) and recorded that the leak remained.
- One Haiku Patch attempt failed with `SCHEMA_INVALID` (`local_test_run_id: String should have
  at most 120 characters`) and its finding ended `unresolved`.
- With the default `--max-tokens 1000000` the run stopped at `BUDGET_EXHAUSTED` after about
  $0.15; eight hypotheses need a larger token budget.

## Platform gaps this surfaced

- The standalone index (`LocalIntel`) does not apply `APIRouter(prefix=...)` and misses a route
  declared with an empty path, so entry points come out as `/search` instead of
  `/tickets/search`. The target declares full paths to avoid this.
- A fix that requires correcting an existing wrong test cannot be delivered; the agents say so
  in their notes, but the run spends every patch attempt first.
- A 120-character limit on `local_test_run_id` can fail an otherwise complete Patch step.

## Limits

- One target, 1-2 runs per model, Python only, GET routes only (the reviewed templates on
  `main` cover no write route).
- Expectations come from the target's `labels.yaml`, which restates the README's rules.
- Total spend for this document: about $4.25.
