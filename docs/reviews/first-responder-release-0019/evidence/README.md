# Reproduction commands and scope

All product code was frozen at `070f75a9987658ef8b816cba412859f7b5c1c948`. Initial upstream test sources were pinned to `0272616eb7e1380dfc0da7b98fa0f2dfe9a1bc53`; final upstream inspected and migration pin are `2c825c4e9e6e1dca305c504fde46cdda0b8cbf16`. Imported files are verified byte-identical at that final upstream head. See UPSTREAM_TEST_PROVENANCE.json for byte-for-byte test provenance. Audit additions do not fix product behavior.

Environment: Python 3.12, existing locked workspace runtime, isolated embedded PostgreSQL 16, scripted model/GitHub transports. `RUN_LIVE_LLM_EVAL=0`, both paid provider key variables blank. Set `PYTHONPATH=backend:shared:standards:monitoring:security-agents:code-intelligence:code-review:specialists`; security suite additionally used previously installed Vercel SDK from isolated `/tmp/ari-review-runtime`.

Commands from audit worktree, with `python` pointing to that environment:

```sh
# Candidate's own full suite, before new audit files were added:
python -m pytest -q backend/tests --ignore=backend/tests/live_defense_e2e/test_release_rereview.py --ignore=backend/tests/test_release_rereview_migrations.py
# Original regressions, production reliability/isolation and migrations:
python -m pytest -q backend/tests/live_defense_e2e/test_independent_integration.py backend/tests/live_defense_e2e/test_exec_reliability_compat.py backend/tests/test_execution_reliability.py backend/tests/test_tenant_isolation_adversarial.py backend/tests/test_ops_readiness.py backend/tests/test_parallel_migrations.py backend/tests/test_release_0019_populated_migration.py backend/tests/test_release_rereview_migrations.py
# Strict retained/new runtime probes (expected five failures until fixed):
python -m pytest -q backend/tests/live_defense_e2e/test_release_rereview.py backend/tests/test_release_rereview_migrations.py
# Exact latest-main production regression tests (expected nine failures):
python -m pytest -q backend/tests/test_upstream_job_compat.py backend/tests/test_upstream_github_compat.py backend/tests/test_upstream_auto_commits_compat.py
# Source privacy compatibility (expected one failure):
python -m pytest -q code-intelligence/tests/test_upstream_privacy_compat.py -k 'redact or secret or credential'
python -m pytest -q security-agents/tests shared/tests tests/security
TSC=/path/to/tsc python -m pytest -q shared/tests/test_contracts.py
python -m shared.export --check
mypy
python deploy/release_readiness.py --out /tmp/ari0019-readiness
```

Standalone PR #2 command (separate worktree at 247c23124ab167e8edf8cafac2d959f1d94b5ca0):
`python -m pytest -q backend/tests/live_defense_e2e/test_exec_reliability_compat.py`.

The readiness script used existing RL dependency site packages and tracked checkpoint, dummy credentials and scratch local processes. No research run or deployed service was invoked. Local sockets/cache startup required escalation; no external security target was tested. Its internal GO is limited to its 25 checks.

`final-probes.log` reruns the strict independent probes and both forward/roundtrip migration checks after formatting (five failed, two passed). The original backend capture predates added audit files; rerunning all tests after adding them deliberately fails. Imported upstream test assertions were not modified. The custom migration adaptation pins the new upstream SHA and tests the supported forward path; upgrading an already-newer database using an older migration tree is not treated as a valid downgrade.

Logs replace known synthetic secret-shaped strings. Synthetic DSN/password examples are evidence, not actual infrastructure credentials. Raw JUnit and browser artifacts are not included. No exact-SHA frontend/browser claim is made. SHA256SUMS.json hashes the retained evidence files.

Final upstream follow-up command (20 failed, 38 passed): `python -m pytest -q backend/tests/test_upstream_redaction_gaps_compat.py backend/tests/test_upstream_pilot_safety_compat.py code-intelligence/tests/test_upstream_privacy_gaps_compat.py`. The final migration-only run passes both latest-main forward and populated roundtrip tests.
