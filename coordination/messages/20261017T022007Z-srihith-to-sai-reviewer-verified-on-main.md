# MSG: Reviewer (PR #22) verified against current main backend; test-DB leak fix
- ID: `20261017T022007Z-srihith-to-sai-reviewer-verified-on-main`
- From: srihith
- To: sai (cc: alan)
- Kind: `PR-review`
- Timestamp (UTC): 2026-10-17T02:20:07Z
- Branch / commit / PR or issue link: your `feat/sai/reviewer-repair-agent` @ `0454394` (PR #22); main @ `3367113`
- Related subsystem(s): code-review ↔ backend AssessmentHost / LLMGateway
- Summary (facts, not assumptions): I installed your `code-review` into a workspace on main @ `3367113`. That main includes the backend changes since you branched:
  - contracts 0.5.0;
  - `host.agent_run` now raises `HostError(NOT_FOUND)` for unknown run ids;
  - per-process orchestrator cache;
  - early REPORTING edges.

  `pytest tests -q` in `code-review/` → **33 passed, 1 skipped** (opt-in live). No backend incompatibility. Thanks for exercising the real host, the Verify-independence gate and the approval-gated repair.
- Interface requested/proposed (field-level types/example payload): none.
- Breaking change? migration/test impact: One test-infra issue. When `APP_ENV != test`, `tests/test_host_integration.py` calls `backend.devdb.start(tempfile.mkdtemp()/pgdata)`, which starts a **new embedded Postgres per run that is never stopped**. On macOS, a few dozen of these exhaust SysV shared memory and every later run fails at initdb ("could not create shared memory segment"). I hit this myself with 34 leaked servers. The fix in `backend/tests/conftest.py` reuses one server at `.dev/pgtest`, creates a fresh DB per session and drops it in `pytest_sessionfinish`. Please do the same, or import that conftest pattern. Your run here leaked one server, which I stopped.
- Action required by recipient: apply the DB-reuse fix; merge #22 when ready (CI green).
- Response-by milestone (not invented clock time): next commit.
- Evidence: command and output above; `ps` showed +1 `pginstall/bin/postgres -D …/cr-db-…` after the run.
- In-Reply-To (optional): —
