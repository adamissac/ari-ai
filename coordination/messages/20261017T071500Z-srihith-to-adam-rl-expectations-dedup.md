# MSG: RL expectations — your #61 implementation kept; mine dropped; real-index test added
- ID: `20261017T071500Z-srihith-to-adam-rl-expectations-dedup`
- From: srihith
- To: adam (cc: all)
- Kind: `integration`
- Timestamp (UTC): 2026-10-17T07:15:00Z
- Branch / commit / PR or issue link: PR #62 (`feat/srihith/rl-expectations`), merging main after #61
- Related subsystem(s): backend RL facts
- Summary (facts, not assumptions): We both closed the same gap in parallel.
  - When I merged main into #62, I kept your `_expectation_inputs` unchanged; my `route_expectations` is removed.
  - Yours is the better version: it never fails the RL job, and it records an `expectations_source` note.
  - This supersedes the RL part of `20261017T065506Z-srihith-to-all-standards-landed-rl-expectations`.
- What #62 still adds:
  1. `backend/tests/test_rl_expectations_real_index.py` checks your code path against Sarosh's **real** payments-lite index in Postgres, not a stub. It asserts:
     - `/payments*` and `/refunds` expectations reach the payments node;
     - `/health` raises gateway criticality from 0.3 to 0.4;
     - an authenticated `rejected` decision restores 0.3.
  2. Alan's item: `build_recipe.json` uses `/payments/{payment_id}` and `/customers/{customer_id}`. `checks/library.py` now binds the route's single named path parameter.
- Breaking change? migration/test impact: none.
- Action required by recipient: none.
- Evidence: `uv run pytest -q backend/tests/test_rl_expectations.py backend/tests/test_rl_expectations_real_index.py` → 4 passed, run locally with `rl_defense` installed. CI skips these tests because it doesn't install `rl_defense`.
- In-Reply-To (optional): `coordination/messages/20261017T070134Z-adam-to-srihith-rl-expectations-wired.md`
