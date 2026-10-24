# Rehearsal evidence — inventory-lite unfamiliar-repo leg (2026-10-24)

Staging-rehearsal evidence for `docs/pilot/FIRST_FIVE_PLAN.md` step 3 on a
repository no scripted fixture or canned model turn is shaped around.

## Fixture

`examples/inventory-lite` — a new FastAPI service (workspaces, items, stock
transfers) authored for this rehearsal. It carries one planted CWE-639-class
ownership defect: `GET /items/{item_id}` omits the `require_owner` call every
sibling route makes. `labels.yaml` is the answer key; `label_checks/` proves the
defect exists and the guarded lookalikes stay safe.

## Executed results

Driven through the real Probe check path (`default_registry` →
`checks.run_template` → `CheckRunner` → driver → rendered pytest in the
check-runner sandbox), committed as
`security-agents/tests/test_inventory_lite_rehearsal.py` (3 passed):

| Check | Route | Result |
|---|---|---|
| `access_control.ownership@1` alice/bob | `GET /items/{item_id}` | `matches_expectation=false`, `test_other_identity_is_denied` fails with `expected one of [403, 404] ... observed 200` — **defect confirmed by execution** |
| `access_control.ownership@1` alice/bob | `GET /warehouses/{workspace_id}` | `matches_expectation=true`, 2 passed — guarded sibling **refuted** |

The result record is serializable executed evidence (`sandbox_run_id`,
`driver=local-process`, `transport=inprocess`, per-test outcomes), not a model
assertion. A Docker-sandbox run of the same check happens through the
`docker-sandbox` CI job on Linux; this macOS box has no Docker daemon, so the
committed test uses the labelled dev driver (`process-dev:not-a-security-boundary`).

## What this does and does not prove

- **Proves**: the reviewed check machinery detects and refutes correctly on a
  repo it has never seen; the fixture is reusable for full end-to-end
  assessments and for the live-model leg of the rehearsal.
- **Still outstanding**: the full seven-agent assessment on this fixture with a
  real provider (`RUN_LIVE_LLM_EVAL=1` + `ANTHROPIC_API_KEY`) — the scripted
  transports are payments-lite-shaped by design and cannot honestly produce
  novel findings here. Canned reference-flow evidence is labelled
  `provider_mode=fake` wherever it is used.
