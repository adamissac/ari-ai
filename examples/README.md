# examples/

> **What exists: nothing yet (Phase 0).** Never deploy anything in this
> directory publicly. See [SECURITY.md](../SECURITY.md).

## Purpose
Deliberately vulnerable demo targets and labeled fixtures that **we own**, used
for the HackATL demo, integration tests and evaluation
([docs/research/EVALUATION_DATASETS](../docs/research/EVALUATION_DATASETS.md)).

## Planned contents
| Path | What | Task |
|---|---|---|
| `payments-lite/` | Small FastAPI service (customers, payments, refunds) with seeded synthetic users; one planted functional bug (refund can exceed original amount) and one planted authorization weakness (a payment-detail route lacks the ownership check its siblings have); a passing but incomplete test suite; `labels.yaml`; sandbox build recipe | DEMO-001 |
| `fixtures/clean-*/` | Small apps without planted issues (negatives) | later |
| `fixtures/bad-patches/` | Patches Verify must reject | SEC-010 |

## Rules
- Planted weaknesses are documented in each target's README and `labels.yaml`
  at the class level (what invariant is broken), not as attack instructions.
- Synthetic data only; no real credentials (fixture secrets are obviously fake).
- Targets run only inside the platform's sandbox network.
- Whether these targets may ever be published is part of the license decision
  ([LICENSE-DECISION.md](../LICENSE-DECISION.md)).

## Interfaces
- `build_recipe` consumed by `security-agents` target builder.
- `labels.yaml` consumed by evaluation scripts and tests.

## Dependencies
Python 3.12, FastAPI (for payments-lite).

## Commands
None yet.
