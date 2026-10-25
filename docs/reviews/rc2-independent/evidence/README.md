# RC2 executable evidence and reproduction

Product commit under review: **3f16c99fb728323ae464890862f84e16981e5f71**. Audit commits add tests/report only; `git diff 3f16c99f -- backend/backend shared/shared frontend security-agents/security_agents code-intelligence/code_intelligence` is empty. The exact commit was fetched explicitly; mutable PR #8 was not used as the execution target.

## Environment

Python 3.12 in an existing workspace runtime, separate `/private/tmp/ari-rc2-review` worktree, embedded local PostgreSQL 16 with disposable per-session databases, Node 24, installed Chrome with fresh test profile. Workspace imports point at the RC2 worktree, not the primary checkout's editable packages. The existing Vercel SDK is supplied from isolated `/tmp/ari-review-runtime` for security tests. Local readiness additionally uses existing Torch/Gym packages and the tracked checkpoint; it does not launch a new research study.

```sh
export PYTHONPATH=backend:shared:standards:monitoring:security-agents:code-intelligence:code-review:specialists
export RUN_LIVE_LLM_EVAL=0 ANTHROPIC_API_KEY= HACKATL_LIVE_ANTHROPIC_API_KEY=
unset REHEARSAL_LIVE
```

Important: RC2's optional live rehearsal gate treats **presence** of REHEARSAL_LIVE as opt-in. The initial `REHEARSAL_LIVE=0` command was incorrect and failed at a missing developer-specific target path before any provider work. The corrected command unsets it. Both outputs are retained. No real API key or customer data was used.

## Suites

```sh
# Initial run, retained as failed evidence:
REHEARSAL_LIVE=0 python -m pytest -q backend/tests
# Corrected original full-suite rerun (new audit tests run separately):
env -u REHEARSAL_LIVE python -m pytest -q backend/tests \
 --ignore=backend/tests/live_defense_e2e/test_rc2_independent.py \
 --ignore=backend/tests/test_rc2_upstream_migrations.py \
 --ignore=backend/tests/test_rc2_populated_migration.py
# Original F1-F10 / concurrency / OFF / tenancy / RLS / migrations:
python -m pytest -q backend/tests/live_defense_e2e/test_independent_integration.py \
 backend/tests/live_defense_e2e/test_exec_reliability_compat.py \
 backend/tests/test_execution_reliability.py backend/tests/test_tenant_isolation_adversarial.py \
 backend/tests/test_customer_security_hardening.py backend/tests/test_ops_readiness.py \
 backend/tests/test_parallel_migrations.py backend/tests/test_rc2_upstream_migrations.py \
 backend/tests/test_rc2_populated_migration.py
# Final adversarial set: known failures intentionally remain strict:
python -m pytest -q backend/tests/live_defense_e2e/test_rc2_independent.py backend/tests/test_rc2_transfer_manifest.py
# Original follow-up assertions + fresh/roundtrip migration proof:
python -m pytest -q backend/tests/live_defense_e2e/test_rc2_independent.py \
 backend/tests/test_rc2_upstream_migrations.py backend/tests/test_rc2_populated_migration.py
# The preceding command in original-independent.log predates new interleaving
# tests; its seven passing cases are the five unchanged original runtime
# probes and two migration tests. Final-adversarial.log includes the new failures.
python -m pytest -q security-agents/tests shared/tests tests/security
python -m pytest -q code-intelligence/tests
TSC=/path/to/tsc python -m pytest -q shared/tests/test_contracts.py
python -m shared.export --check
mypy
python deploy/release_readiness.py --out /tmp/rc2-readiness
```

From frontend:

```sh
npm ci --ignore-scripts --offline --no-audit --no-fund
npm ci --prefix transport --ignore-scripts --offline --no-audit --no-fund
npm run build --prefix transport
npm run test --prefix transport
npm test
npm run typecheck
npm run lint
NEXT_PUBLIC_DEV_LOGIN=1 npm run build
RUN_LIVE_LLM_EVAL=0 ANTHROPIC_API_KEY= HACKATL_LIVE_ANTHROPIC_API_KEY= \
 E2E_BROWSER_CHANNEL=chrome E2E_SKIP_BUILD=1 \
 PYTHONPATH=../backend:../shared:../standards:../monitoring:../security-agents:../code-intelligence:../code-review:../specialists \
 python tests/e2e/stack.py
```

`test_worker_drain.py` was rerun unchanged in isolation after its initial failure. A separate readiness-synchronized control waits for actual job entry, then enforces the same SIGTERM/exit-zero/finished-once outcome. The control does not replace or xfail the original tests.

Current-main compatibility checks are separate from RC2's base assertions:

```sh
python -m pytest -q backend/tests/test_rc2_latest_quota.py -k 'over_limit_hourly_assessments_report_actual_reset or over_limit_daily_assessments_report_actual_reset'
python -m pytest -q security-agents/tests/test_rc2_latest_protected.py::test_verify_rejects_a_planted_bad_patch_that_edits_a_protected_test
```

The quota source is pinned to upstream 4d4be9e3, protected-test source to 95e90861. They demonstrate newer upstream behavior absent from the frozen candidate; retain these upstream changes in the eventual merge rather than replacing them with RC2 files.

## Transfer checks

Exact refs and changed-path lists are in transfer-scope.json. The strict manifest test reads pinned Git objects with `git show`, not mutable branch contents. Fetch the listed exact transfer commits from `https://github.com/m-alan08/ari-ai.git` before reproducing in a new clone. It proves duplicate 0018 declarations and invalid schema value types without importing an incomplete standalone branch.

`squash-simulation.json` records `git merge-tree --write-tree --messages` starting at 4d4be9e3. Documentation-conflicted trees were attached to **unreferenced local virtual single-parent commits** for the next simulation step; no branch, HEAD or working-tree production file was merged. Simulation stops at reliability's production worker/control conflicts. It does not claim a completed conflict resolution or a final equivalent release tree.

## Evidence integrity

Original prior runtime assertions were copied from audit commit 005ea42d; only additional tests were appended. Original F1-F10 assertion diff and test AST checks are recorded. Synthetic known token patterns are replaced in retained text output; raw JUnit, real credentials and customer artifacts are not included. Sanitized diffs remain explanatory snapshots; immutable Git source SHAs are the authority. SHA256SUMS.json hashes retained evidence. Suite counts overlap and must not be summed.
