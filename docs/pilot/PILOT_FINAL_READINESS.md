# Pilot Final Readiness — Ari AI first-customer pilot

> **Status: DRAFT / checkpoint — current recommendation: NO-GO (pending).**
> Living document written by the pilot-completion-commander (Adam lane, Devin session
> `89af211994aa458d96ecf9f412c05bd7`). Each claim is labelled with how it was proven, and
> results reported by other agents are kept separate from ones re-run here.
> Last updated: 2026-10-25T01:35Z.

## 1. Versions under test

| Component | Version | How observed |
|---|---|---|
| `main` | `dc9a623a` (includes #530 `22454ef2`, #531 `ac87a290`, #567 `5a56e44c`) | `git fetch` 2026-10-25T01:10Z |
| Railway API `ari-ai-production-76d4.up.railway.app` | `git_sha=dc9a623a…`, `schema_version=0.22.0` | `GET /healthz` 01:10Z |
| Vercel frontend `ari-ai-lake.vercel.app` | landing page serves; deployed SHA not yet pinned | browser |
| DB migrations | single Alembic head `0017` (verified locally on `5a56e44c`) | `backend.migrate.alembic_config()` |

## 2. Binding pilot conditions

Legend: **PASS-local** = real code + real Postgres on a dev machine, scripted LLM ·
**PASS-prod** = observed on the deployed stack · **REPORTED** = another agent's evidence, not yet
re-run here · **OPEN** = not proven · **FAIL** = defect reproduced.

| # | Condition | Owner | Method | State |
|---|---|---|---|---|
| C1 | `main` boots, migrates, suite green | integration-lead | `make check`, `make test`, boot, curl | **PASS-local** on `5a56e44c`: 828 passed / 16 skipped / 0 failed (4m49s); ruff/format/contract checks pass; `/healthz` 200, `/readyz` 200, `/diagnostics` 401 unauth / 200 owner. **Re-verified PASS-local on `dc9a623a`: 832 passed / 16 skipped / 0 failed (313s)**, fresh DB migrated to single head `0017` |
| C2 | Prod API healthy on exact deployed SHA | integration-lead | `/healthz`, `/readyz` | **PASS-prod (readiness only)**: SHA matches; db/queue ok; 12 workers heartbeating; llm=live `claude-haiku-5-5`; GitHub App/OAuth/webhook configured; sandbox=vercel; artifact store writable. Readiness alone does not show that an assessment completes (see C4) |
| C3 | Prod queue drains | integration-lead | read-only prod DB (Adam-provided URL, `default_transaction_read_only=on`) 01:30Z | **Diagnosed — not stuck, but churning**: of 359 queued jobs, 354 are `assess_github_commit` with `run_after` in the future, all sharing one timestamp (01:30:28Z) and dedupe `github:deferred:<job>`. When that time arrives they all become due together, capacity admits ≤1, and the rest re-enqueue. That makes ~3–4k jobs/h (7,134 of 7,419 assess jobs in 2h were deferral re-enqueues); totals 16,211 succeeded, 56 failed, 0 dead. The backlog cannot drain at 5/h. Accepted pilot limitation; post-pilot fix is to collapse deferrals per repo to the newest SHA |
| C4 | Hosted customer journey (OAuth → connect → index → scope → manual assessment → 7 roles → validated planted vuln → fix → human approval → PR → independent verify → dashboard persistence) | pilot-completion-commander | Real browser on `ari-ai-lake.vercel.app` + `adamissac/pilot-rehearsal-target` | **OPEN — blocked on Adam's GitHub OAuth sign-in in the session browser**. Target repo: private, App installed, `main`=`256c8e8c` (Ari build-recipe PR #1 merged by `ari-security[bot]` 00:40Z). Webhook 202 at 00:07Z is not counted as evidence |
| C5 | Two-org isolation | rehearsal owner | `backend/tests/test_pilot_rehearsal.py` | **REPORTED PASS-local** (34 probes, uniform 404) in [REHEARSAL_REPORT](REHEARSAL_REPORT.md); test is in the 828-pass suite above. Prod two-org probe: **OPEN** |
| C6 | Secret redaction: code-intel index/context (`code_intelligence/privacy.py`) | integration-lead (fixing) | 17-case probe: leak / `ast.parse` / line count | **FAIL on main**: parse and line count preserved in 17/17, but the secret value survives in 10 classes: `*_token` names, bare `token`, Stripe `sk_live_`, `postgresql://u:p@`, JWT, Google `AIza`, paren-concat multiline, 2nd tuple element, `os.environ.get(..., default)`, digit-less mid-line kwarg |
| C7 | Secret redaction: `jobs.last_error` (`backend/redaction.py`) | integration-lead (fixing) | direct `redact_text` probe | **FAIL on main**: `postgresql+psycopg://admin:<pw>@…` not scrubbed; `access_token=`, `DB_PASSWORD=`, `client_secret:` not scrubbed |
| C8 | Dead-letter jobs endpoint authz | release-gate owner | code review | **PASS (code review)**: `require_project` → 404 for non-members; owners get redacted error, other members coarse code/category. **PASS-local runtime** on `dc9a623a`: owner 200 (dead+failed items), non-member 404 |
| C9 | `purge_project` deletion | rehearsal owner | `test_purge_project_deletes_every_surface` | **REPORTED PASS-local**; prod/faithful-disposable run: **OPEN** |
| C10 | #412 / #458 not merged | integration-lead | PR state | **PASS**: both open, held for human security review |
| C12 | Prod availability | Adam / integration-lead | `/healthz`, pg_stat_activity | **FAIL (in progress)**: 502 since ~01:27Z after main→`2c8ad50d` (#571); Railway check green; DB shows no API/worker connections; last heartbeat 01:26:51Z |
| C13 | Prod identity integrity | rehearsal owner / Adam | read-only DB | **OPEN — security flag**: synthetic users `rehearsal-alice`/`rehearsal-eve` created in prod 01:28:42Z; `rehearsal-alice` is **owner** of `org_01M55VPKH8T3P1WWEB73YQ8RDS` (adamissac personal, owns the rehearsal repo); no audit event for the grant. How it was created is unconfirmed. If a non-OAuth prod login path exists → NO-GO |
| C14 | DB tenant enforcement | backend owner | read-only DB | **Finding**: the app role is `postgres` (`rolsuper`, `rolbypassrls` = true); RLS is enabled on 2/47 public tables, so tenant isolation is enforced only by the application layer (C5) |
| C15 | Storage | Adam / infra | read-only DB | DB 3,398 MB, of which `index_payloads` is 3,320 MB; retention policy for index payloads not yet verified |
| C11 | Branch protection | Adam | GitHub settings | **Limitation**: not available on this personal private repo; human-reviewed merges by integration-lead ([BRANCH_PROTECTION_LIMITATION](BRANCH_PROTECTION_LIMITATION.md)) |

## 3. Code intelligence — reproduced on `5a56e44c` (code of #531)

Command: `PYTHONPATH=code-intelligence:shared .venv/bin/python code-intelligence/evidence/index_benchmark.py <repo> <sha> [prefix]`.
Local machine, single run, no LLM.

| Target | Files parsed | Imports | Routes | Call edges | Time | Py heap peak |
|---|---|---|---|---|---|---|
| `examples/payments-lite` | 9 | 52/52 | 8/8 | 198 | 0.25 s | 3.6 MB |
| `backend/` | 146 | 2549/2549 | 112/114 + 2 flagged | 9,594 | 5.1 s | 107 MB |
| whole repo | 533 | 8426/8426 | 137/139 + 2 flagged | 29,117 | 22.2 s | 494 MB |

Whole-repo call-edge resolution: **exact 7,747 (26.6%) · likely 580 (2.0%) · unresolved 20,790 (71.4%)**.
This is the same ~72% unresolved reported earlier, so the problem has not improved. Breakdown of the unresolved edges (heuristic classifier over `callee_name`):
attribute call on a local variable/expression 47.1%, stdlib/third-party module 20.1%,
builtin 18.9%, bare local/closure/imported name 11.6% (top: `Field`, `Path`, `client_factory`,
`timedelta`, `dataclass`), `self`/`cls` attribute 2.3%. About 39% (stdlib/3rd-party + builtins)
cannot resolve to repository symbols by design. The two non-literal routes (`FIXTURE_ROUTE`,
`CONTROL_PATH`) are now reported as index issues instead of being dropped silently. Retrieval recall
(82% payments-lite / 63% Ari, from #531's PR) has **not yet been re-run here**.

## 3b. Seven-agent pipeline and functional reviewer — scripted/replay evidence on `dc9a623a`

Every result in this section uses **scripted model turns (`provider_mode=fake`) with real tools**. None of it is live-provider or prod evidence.

- `security-agents` suite: **594 passed / 24 skipped / 0 failed** (skips: 11 Docker sandbox, 11 live opt-in, 2 import/compat). The first attempt in a fresh venv failed with `No module named 'yaml'`; it passed after `pyyaml` was installed. `security_agents/intel/labels.py` imports `yaml` lazily, but `security-agents/pyproject.toml` does not declare it. The workspace gets it only through `hackatl-code-review`, so the workspace/prod install is fine and the standalone README install breaks (minor; doc/dependency fix).
- Replay `security_agents.cli --target ../examples/payments-lite --auto-approve`: Scout, Probe, Trace, Diagnose, Fortify, Patch and Verify all `succeeded`; final finding `hardened`.
- `code-review` suite: **90 passed / 4 skipped**; `code_review.eval_corpus`: 10/10 labels `ok`. The corpus is the tuned fixture set. It is **not** an independent held-out evaluation, so it says nothing about real-world reviewer accuracy (still **OPEN**).
- Tests that cover each failure mode: invalid structured output (retried once, then the step fails), provider outage → `LLM_UNAVAILABLE`, retries, inconclusive Probe, false positive refuted by executed evidence, ineffective/out-of-plan/test-weakening patches rejected, Verify rejecting bad patches, cancellation, token/USD/turn budgets, and honest `unresolved` final states. **Gap: no test for a provider timeout specifically.** None of these failure modes has been exercised against the live provider.
- Live seven-role evidence (REPORTED, not re-run here): all roles live on `examples/inventory-lite`, planted IDOR confirmed and hardened, $0.0334 (#555).

## 4. Open human-only actions

1. **Adam**: complete GitHub OAuth in the session browser on `ari-ai-lake.vercel.app` (needed for C4, and for owner `/diagnostics` to settle C3).
2. **Adam**: give the operator read access to the prod queue (owner diagnostics or Railway DB read-only), or inspect it yourself: `SELECT kind, status, run_after > now() AS deferred, count(*) FROM jobs WHERE status='queued' GROUP BY 1,2,3;` (read-only).
3. **Adam**: separate human security review before #412/#458.

## 5. Recommendation

**NO-GO (pending)**. C4 (hosted journey) and C6/C7 (redaction FAIL on main) block a GO.
C3 must be settled. When those pass, the expected outcome is a CONDITIONAL GO, with C11 and the
code-intelligence limitations in §3 as accepted limitations.
