# inventory-lite — second owned evaluation/rehearsal fixture

A small, deliberately defective FastAPI service used for **pilot staging
rehearsals**: it was authored after the platform's scripted fixtures were fixed,
so no agent script, canned LLM turn, or check parameter is shaped around it.
That makes it the honest "unfamiliar, authorized Python repository" required by
`docs/pilot/FIRST_FIVE_PLAN.md` step 3 — a real defect must be discovered and
validated by execution, not replayed from a script.

Layout mirrors `examples/payments-lite`:

- `target/` — the app the platform indexes and builds (planted CWE-639-class
  ownership defect on `GET /items/{item_id}`; sibling routes enforce ownership).
- `build_recipe.json` — operator-approved sandbox recipe consumed by
  `security_agents` (fixture identities, resources, routes a reviewed check
  template may name; not an answer key).
- `labels.yaml` — ground-truth answer key for evaluation, kept outside `target/`.
- `label_checks/` — proves the planted defect still exists and lookalike routes
  stay safe; run `target/.venv/bin/python -m pytest -q label_checks` from here.

The committed check-level rehearsal lives at
`security-agents/tests/test_inventory_lite_rehearsal.py`: it drives the real
`checks.run_template` path against this fixture and asserts the defect is
*confirmed by execution* while the guarded sibling is refuted.
