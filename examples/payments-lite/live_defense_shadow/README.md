# payments-lite Live Defense Phase 3 shadow fixture

Owned staging replay for Ari Live Defense. All traffic is synthetic counters from
this repository's `payments-lite` target. There are no third-party systems and no
production attacks.

Ground truth is in `ground_truth.json`. Replay:

```
# Register an owned_test app, mint an ingest token (shown once), then:
uv run python examples/payments-lite/live_defense_shadow/replay.py \
  --api http://127.0.0.1:8000/api/v1 \
  --project "$PROJECT_ID" \
  --token "$INGEST_TOKEN"
```

Then drain the worker (`uv run python -m backend.worker --once`) and open
`/projects/$PROJECT_ID/live-defense`. Shadow decisions show as authenticated,
NOT EXECUTED. Analyst accept does not apply a control.
