# Staging Rehearsal Report

- **Rehearsal date:** 2026-10-24
- **Code under test:** `adamissac/ari-ai` `main` @ `d0131167` (+ rehearsal test file on `docs/adam/pilot-launch` @ `c297b033` and later)
- **Environments:** (a) production — Railway API `ari-ai-production-76d4.up.railway.app` + Vercel frontend `ari-ai-lake.vercel.app` + real GitHub App + live Anthropic; (b) local real stack — FastAPI TestClient + real PostgreSQL + in-process worker + scripted `FakeTransport`.
- **Honesty rule (per Adam):** each stage is labelled `live Claude` / `scripted` / `sandbox` / `real I/O`. Nothing skipped is claimed as passed.

## Result summary

| # | Verification | Leg | Result |
|---|---|---|---|
| 1 | Tenant isolation (cross-org ID substitution) | Local real stack | **PASS** — 34 probes, uniform 404, no existence leak |
| 2 | Real execution / labelling | Local + prod | **PASS (partial)** — scripted stages labelled; prod labelling pending |
| 3 | GitHub safety (PR/manual only, scoped write tokens, no auto-merge) | Code audit + prod | **PASS (code-verified)**; prod fix-PR delivery pending |
| 4 | Monitoring: opt-in controls, limits, cancel, budget caps | Local + code | **PASS** |
| 5 | Defense Lab: recommendation-only | Code + tests | **PASS** |
| 6 | Data privacy: storage, provider processing, artifacts, deletion | Local + code | **PASS (documented)** — operator-run procedure verified |
| 7 | Reliability: failure recovery, persistence, restarts, UI errors | Local + suite | **PASS** |
| P1 | Prod journey: install → connect → index → live assessment → fix PR → verify | Prod | **BLOCKED — awaiting rehearsal repo + session credential** |

## Leg 1 — Two-org isolation (real stack, scripted LLM)

**Test:** `backend/tests/test_pilot_rehearsal.py::test_two_org_isolation_by_id_substitution`.
Real FastAPI app + real PostgreSQL + real worker (`worker.drain`), two independent
personal orgs (alice+bob vs eve), full scripted seven-agent loop completed first so
every resource type genuinely exists.

**Probe matrix (eve, authenticated non-member, substituting org-A IDs):** project,
repo list/detail, commits, snapshots list+POST, scopes list, scope approve+revoke,
assessments list+POST+GET+runs+events+events/log+report+RoE+cancel, findings
list+detail+patches+accept-risk, artifacts (diff + LLM transcript), project events,
reassessments, approvals, defense-recommendations, defense-health, pilot-report,
ingest-tokens, applications, control-grants, context-pack POST, jobs, plus
fabricated `fnd_/asm_/art_` IDs.

**Result:** every probe → **404** (uniform not-found, no existence leak). Eve's own
API works (200) with empty lists — isolation, not broken auth. Context-pack POST on
a foreign project is denied. `provider_mode=fake` is asserted on every agent run —
scripted turns are identifiable in stored data, matching the "labelled" contract.

## Leg 2 — Monitoring controls, cancel, opt-out

`test_cancel_optout_and_reoptin_drills` + existing
`test_cancel_before_start_and_revoke_stops_assessments`:

- `POST /assessments/{id}/cancel` → terminal `CANCELLED`; second cancel → honest 409.
- `PATCH /repositories/{id} automatic_assessments=false` → subsequent webhook push
  yields **zero** reassessments; re-enabling restores the trigger.
- Scope `revoke` → outstanding assessment `CANCELLED`, new ones `SCOPE_DENIED`.
- Budgets (code-verified): 400k tokens / $10 / 1800s per manual assessment; 150k /
  $3 / 900s monitoring; 5 starts/hour; 60 req/min API; auto runs deferred at 5/h &
  20/d per project; $50/day global auto cap.

## Leg 3 — Operator deletion procedure

`test_operator_deletion_procedure`. **Finding:** foreign keys have **no cascades**
— there is no single-row delete. The canonical operator entry point is
`purge_project` (`backend/privacy.py`, landed via PR #535 +
[docs/security/TENANT_DATA_PROTECTION.md](../security/TENANT_DATA_PROTECTION.md)),
which performs the org-scoped teardown below:

1. Delete org-scoped rows across every table having `organization_id` (enumerated
   via `information_schema`), child tables first (FK-safe order or a maintenance
   transaction).
2. Delete `repositories` and `projects` rows.
3. Delete disk objects: artifact files under `$ARTIFACT_STORE_URI` (**note:**
   content-addressed sharing means cross-tenant refcounting is required before
   unlinking — an open gap, R-11-adjacent) and the bare clone at
   `$SECURITY_WORKDIR/repos/{repo_id}.git`.
4. Verify: after the drill every endpoint (project, repo, assessment, finding,
   events) returned 404.

**30-day SLA enforcement (operational):** deletion requests are logged in
`coordination/DELETION_LOG.md` (to create) with timestamp + requestor; an operator
runs the procedure above, records completion, and the SLA clock is tracked by a
weekly automation checking open requests older than 25 days. There is no
self-serve deletion and no automated purge — this is disclosed in
`DATA_HANDLING.md`.

## Leg 4 — Reliability

- Worker-death job reclaim: `test_a_claim_held_by_a_job_that_stopped_running_can_be_reclaimed` — PASS (lease expiry lets another worker resume; no stranded assessment).
- Persistence: all assessment/agent/artifact/finding state is Postgres + artifact store; report served "from persisted records".
- UI error reporting: frontend `assessment-recovery.test.tsx` + error/retry states covered in the 135-case vitest suite; API returns structured `error.code` envelopes.
- `readyz` on production: database/queue/llm_mode=github_app/webhook_secret all healthy (checked 2026-10-24).

## Leg 5 — GitHub App permissions reconciliation

- Deploy doc previously claimed **Contents read-only** — wrong. Actual requirement:
  Contents **read+write** and Pull requests **read+write** at app level.
- Tokens are least-privilege per call: read tokens `{contents:read, metadata:read}`;
  write tokens `{contents:write, pull_requests:write, metadata:read}` pinned to a
  single repository; 1h GitHub TTL, ~50min in-memory cache, never persisted.
- Fix delivered via PR/manual delivery modes only; `auto` exists in the enum but
  is not enabled for pilot (pilot mode = manual/PR). Nothing merges or deploys.
- Doc fix committed to `docs/deploy/RAILWAY_AND_GITHUB_APP.md` (PR #527).

## Leg 6 — PR #441 (redaction parse fix) — reviewed

Mergeable. Fixes a real defect: `redact()` broke Python syntax on 36 files,
silently dropping them from indexing. Includes a regression test; discloses a
residual gap (unquoted values followed by more code on the same line are no
longer redacted; token-format patterns still catch real keys). **Recommendation:
merge before indexing pilot customer code.**

## Leg 7 — Production journey (LIVE)

**Status: blocked pending two inputs** (requested from owner 2026-10-24):

1. `adamissac/pilot-rehearsal-target` — empty private repo + GitHub App installed.
   Prepared target: `ledgerlite` FastAPI service with a planted access-control
   defect (`GET /accounts/{id}` lacks the ownership check) so the
   `access_control.ownership` template can validate end-to-end; 6 unit tests pass
   locally.
2. `ARI_PROD_SESSION` — `hackatl_session` cookie for the Vercel deployment.

Once unblocked: connect repo → snapshot/index → manual assessment (live Claude,
bounded by the 400k/$10 cap) → findings → approval → PR delivery → verify →
results retrieval → revoke.

## Open findings for the launch decision

1. **No automated retention; deletion is operator-invoked** — `purge_project`
   performs the multi-table teardown (no FK cascades) + disk objects; artifact
   store needs refcounting before per-tenant unlink. Drill verified the data is
   gone afterward (uniform 404). No self-serve delete or TTL.
2. **Only 3 executable Probe check templates** — other CWEs are flagged-not-validated; must be reflected in customer-facing claims (done in FEATURE_MATRIX).
3. **Isolation = membership checks + RLS on source-content tables** — RLS now
   guards `index_payloads`/`artifacts` (PR #535); membership checks remain the
   primary boundary elsewhere and are covered by the ID-substitution drill.
4. **Assistant-role turns are re-sent unredacted** to the provider (thinking-block
   signature constraint) — disclosed; mitigated by inbound redaction.
5. **Prod leg not yet executed** — this report is CONDITIONAL until Leg 7 lands.
