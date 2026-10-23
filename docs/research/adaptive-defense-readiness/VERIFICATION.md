# Executed verification and research boundary

Code/research snapshot: `6c833795060f27b85605f229f1b83f7acd761c48`.
PR: https://github.com/adamissac/ari-ai/pull/422 (CI/review/merge state lives there).

Local Python: existing trusted Python3.12.14 RL venv; no new dependency installation.
Paths below are repository-relative command arguments; use the repo root.

- `PYTHONPATH=rl-defense:shared:standards:examples/payments-lite/target RUN_LIVE_LLM_EVAL=0 python -m pytest rl-defense/tests/test_adaptive_readiness.py rl-defense/tests/test_authorization_provider.py rl-defense/tests/test_payment_read_lab.py rl-defense/tests/test_research_authorization.py rl-defense/tests/test_constrained_research.py rl-defense/tests/test_feasibility_readiness.py -q`
  — **166 passed in19.80s** on committed code. Includes22 new causal/readiness tests.
- `TSC=/path/to/frontend/node_modules/typescript/bin/tsc PYTHONPATH=shared:standards python -m pytest shared/tests -q`
  — **91 passed in0.96s**, including TypeScript; no skipped contract check.
- `MYPYPATH=rl-defense:shared:standards mypy --strict --follow-imports=silent --ignore-missing-imports rl-defense/rl_defense/research/adaptive.py rl-defense/rl_defense/research/adaptive_readiness.py`
  — **success, two source files**. This is scoped type checking, not a full-repo
  strict-type claim. Imported pre-existing modules are followed silently.
- RL Ruff check and format check — all pass;102 files formatted at initial check,
  changed modules/tests checked again after the late-arrival correction.
- `python scripts/check_links.py` — zero broken links; final count changes with docs.
- `python -m rl_defense.research.adaptive_readiness` — fixed read-only train inventory;
  equality to DATASET_AUDIT.json is enforced by the tests. No policies execute in it.
- `git diff --check` — pass. No changes under historical results, runs, layouts,
  checkpoint/registry, shared contracts, backend or deployment relative to base main.
- Original live registry SHA256 remains
  `c345593354856c50559ba16611853a0e4936a7efc11fa5704c224d3189271408`.

One pre-commit broad regression attempt had165 passes and one rejection because the
late-arrival source edit was not yet committed; the existing Git-source fingerprint
check correctly rejected the mismatch. No guard was weakened. Commit6c833795 and
rerun produced the166-passing result above. Earlier164-test run passed before adding
the two late-arrival/forbidden-label regressions. These are not new independent data.

Regression suites execute existing tiny authored baseline/HTTP fixtures; standard RL
CI also includes gradient/update unit tests and its existing20k-step smoke/reload.
Those are software regression checks, not a new experimental comparison, new scenario
collection, candidate checkpoint training or preregistered research run. No holdout
is rerun, new model selected, serving checkpoint registered, or promotion performed.

Required CI/backend integration and review status must be read on PR422; this file
does not fabricate results before those jobs finish. Documentation-only descendants
may update handoff/status without changing the tested code fingerprint. No dedicated
independent research approval or residual-task approval is implied by green checks.

Final boundary follow-up: the adapter now uses a strict availability cutoff and
half-open arrival windows. Evidence stamped exactly at the action cutoff belongs
to the next window, preventing same-tick lookahead with coarse timestamps.
The new targeted suite is23 tests, all passed in1.18s; scoped strict mypy passes.
This is a source change after6c833795, so that earlier166-test receipt is historical;
read PR422 for final-head regression/CI results rather than treating it as unchanged
code. No additional research data or policy evaluation is involved.
