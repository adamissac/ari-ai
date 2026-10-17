# payments-lite (owned, deliberately flawed demo target)

Small FastAPI payments service used for HackATL integration tests and the demo.
**Never deploy it.** It runs only inside the platform sandbox with synthetic
fixture customers (`alice`, `bob`) and in-memory data.

## Intended behaviour (specification)

- Customers authenticate with a bearer token; every `/payments` route requires it.
- Tenant isolation: a customer can read only payments (and refunds) they own;
  any other customer's payment is reported as not found (404).
- Refunds: the total refunded for a payment must never exceed the original
  payment amount; an over-refund request must be rejected with a 4xx error.

## Planted defects (class level only)

See `labels.yaml`. One authorization weakness (a route that does not apply the
ownership condition its sibling routes apply) and one functional defect (a
business-rule bound that is not enforced). Sibling routes that *do* enforce
ownership are intentional look-alikes for precision measurement.

## Layout

| Path | Purpose |
|---|---|
| `payments_lite/` | app factory `create_app()` and in-memory store |
| `tests/` | existing suite: passes, but incomplete |
| `build_recipe.json` | sandbox build recipe consumed by `security_agents` (identities, resources, routes) |
| `expectations.json` | hand-labelled behavioural expectations (fixture until INTEL-007) |
| `labels.yaml` | ground-truth labels for evaluation |

## Commands

```bash
cd examples/payments-lite && python -m pytest -q tests
```
