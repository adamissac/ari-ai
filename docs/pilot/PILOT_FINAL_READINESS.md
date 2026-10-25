# Pilot Final Readiness — Ari AI first-customer pilot

> **Status: DRAFT / checkpoint — current recommendation: NO-GO (pending).**
> Living document written by the pilot-completion-commander (Adam lane, Devin session
> `89af211994aa458d96ecf9f412c05bd7`). Each claim is labelled with how it was proven, and
> results reported by other agents are kept separate from ones re-run here.
> Last updated: 2026-10-25T01:20Z.

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
| C1 | `main` boots, migrates, suite green | integration-lead | `make check`, `make test`, boot, curl | **PASS-local** on `5a56e44c`: 828 passed / 16 skipped / 0 failed (4m49s); ruff/format/contract checks pass; `/healthz` 200, `/readyz` 200, `/diagnostics` 401 unauth / 200 owner. Re-verification on `dc9a623a`: in progress |
| C2 | Prod API healthy on exact deployed SHA | integration-lead | `/healthz`, `/readyz` | **PASS-prod (readiness only)**: SHA matches; db/queue ok; 12 workers heartbeating; llm=live `claude-haiku-5-5`; GitHub App/OAuth/webhook configured; sandbox=vercel; artifact store writable. Readiness alone does not show that an assessment completes (see C4) |
| C3 | Prod queue drains | Adam (human access) | owner `/diagnostics` or DB read | **OPEN**: `queued_jobs` 242 → 252 with `running_jobs=0`, `busy=0`. In code, only `auto_commits` capacity deferral (5/h, 20/d per project) and live-defense controls enqueue with a future `run_after`, and the claim SQL only takes `run_after <= now()`, so idle workers plus a large deferred backlog is the expected signature. Not confirmed: `queue_counts` does not split queued jobs into due vs deferred |
| C4 | Hosted customer journey (OAuth → connect → index → scope → manual assessment → 7 roles → validated planted vuln → fix → human approval → PR → independent verify → dashboard persistence) | pilot-completion-commander | Real browser on `ari-ai-lake.vercel.app` + `adamissac/pilot-rehearsal-target` | **OPEN — blocked on Adam's GitHub OAuth sign-in in the session browser**. Target repo: private, App installed, `main`=`256c8e8c` (Ari build-recipe PR #1 merged by `ari-security[bot]` 00:40Z). Webhook 202 at 00:07Z is not counted as evidence |
| C5 | Two-org isolation | rehearsal owner | `backend/tests/test_pilot_rehearsal.py` | **REPORTED PASS-local** (34 probes, uniform 404) in [REHEARSAL_REPORT](REHEARSAL_REPORT.md); test is in the 828-pass suite above. Prod two-org probe: **OPEN** |
| C6 | Secret redaction: code-intel index/context (`code_intelligence/privacy.py`) | integration-lead (fixing) | 17-case probe: leak / `ast.parse` / line count | **FAIL on main**: parse and line count preserved in 17/17, but the secret value survives in 10 classes: `*_token` names, bare `token`, Stripe `sk_live_`, `postgresql://u:p@`, JWT, Google `AIza`, paren-concat multiline, 2nd tuple element, `os.environ.get(..., default)`, digit-less mid-line kwarg |
| C7 | Secret redaction: `jobs.last_error` (`backend/redaction.py`) | integration-lead (fixing) | direct `redact_text` probe | **FAIL on main**: `postgresql+psycopg://admin:<pw>@…` not scrubbed; `access_token=`, `DB_PASSWORD=`, `client_secret:` not scrubbed |
| C8 | Dead-letter jobs endpoint authz | release-gate owner | code review | **PASS (code review)**: `require_project` → 404 for non-members; owners get redacted error, other members coarse code/category. Runtime cross-org probe: in progress |
| C9 | `purge_project` deletion | rehearsal owner | `test_purge_project_deletes_every_surface` | **REPORTED PASS-local**; prod/faithful-disposable run: **OPEN** |
| C10 | #412 / #458 not merged | integration-lead | PR state | **PASS**: both open, held for human security review |
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

## 4. Open human-only actions

1. **Adam**: complete GitHub OAuth in the session browser on `ari-ai-lake.vercel.app` (needed for C4, and for owner `/diagnostics` to settle C3).
2. **Adam**: give the operator read access to the prod queue (owner diagnostics or Railway DB read-only), or inspect it yourself: `SELECT kind, status, run_after > now() AS deferred, count(*) FROM jobs WHERE status='queued' GROUP BY 1,2,3;` (read-only).
3. **Adam**: separate human security review before #412/#458.

## 5. Recommendation

**NO-GO (pending)**. C4 (hosted journey) and C6/C7 (redaction FAIL on main) block a GO.
C3 must be settled. When those pass, the expected outcome is a CONDITIONAL GO, with C11 and the
code-intelligence limitations in §3 as accepted limitations.
