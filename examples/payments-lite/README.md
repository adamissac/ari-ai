# payments-lite — demo target and answer key

> **Deliberately vulnerable, owned by this project.** Synthetic data only. Never deploy
> anywhere public; run it only inside the platform's sandbox ([SECURITY.md](../../SECURITY.md),
> [docs/15](../../docs/15_SECURITY_BOUNDARIES.md)).

| Path | What it is | Who reads it |
|---|---|---|
| [`target/`](target/README.md) | The app the platform indexes, reviews, builds and tests. No hints inside. | The platform (point ingestion at `target/` only) |
| [`labels.yaml`](labels.yaml) | Answer key: expectations, planted findings, negatives, fixture identities | Evaluation scripts, tests, humans |
| [`label_checks/`](label_checks/test_planted_defects.py) | Tests proving the planted defects exist and the lookalikes are safe | CI, anyone changing `target/` |

## Planted defects (class-level)

| Id | Kind | Where | Broken invariant |
|---|---|---|---|
| `fnd_planted_authz` | security (CWE-639) | `GET /payments/{payment_id}` | "A customer can only read payments they own": unlike its sibling routes, the handler never checks ownership |
| `fnd_planted_refund_bound` | functional (CWE-840) | `POST /refunds` | "Total refunds must never exceed the original amount": only the new refund is compared with the payment amount |

Three **negatives** (lookalike routes that are correct) measure precision; see `labels.yaml`.
The target's own test suite passes on the buggy code: neither defect is tested.

## How each pillar uses it

- **Code intelligence (Sarosh):** index `target/` at a commit; expected to derive
  `exp_owner_only` (from docstring, README and the `require_owner` convention) and `exp_refund_bound`.
- **Review & repair (Sai):** a generated behavioral test for `exp_refund_bound` should fail
  before the fix and pass after.
- **Security agents (Alan):** Scout should raise the ownership hypothesis on
  `GET /payments/{payment_id}`; Probe validates it with an `access_control.ownership` check
  using the two fixture identities; the negatives should be refuted.
- **RL (Adam):** [`rl-defense/configs/topology/payments_lite.yaml`](../../rl-defense/configs/topology/payments_lite.yaml)
  maps these routes onto the simulator's nodes.

## Commands

```bash
cd examples/payments-lite/target
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]" pyyaml
.venv/bin/python -m pytest -q                 # target's own tests (pass; defects untested)
cd .. && target/.venv/bin/python -m pytest -q label_checks   # planted defects exist
docker build -t payments-lite:dev target      # sandbox build recipe (non-root, port 8080)
```

**Not verified yet:** the Docker build (Docker was not available on the machine that
built this; please run it once and report).
