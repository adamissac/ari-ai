# Launch decision — first five pilot customers

**Decision: NO-GO**

## Blocking conditions (2026-10-25)

- No fix PR has been delivered on production. Hosted run `asm_01M5RCVC20ZMYH8EKTZQP40W73` completed all seven roles on the planted IDOR, but `deliver_verified_patch` failed closed ("the stored diff was redacted; Verify tested different bytes"). Fixes: `fix/adam/redaction-code-safe`, `fix/adam/sealed-verified-diff`, `fix/adam/patch-fixture-reuse`.
- Both production assessments were started by the synthetic account `rehearsal-alice`, not a real customer identity.
- The production application connects to PostgreSQL as a superuser with BYPASSRLS, so row-level security is inert.
- No genuine user has completed the intended end-to-end flow through the website.

Evidence: `docs/pilot/PILOT_FINAL_READINESS.md` on `docs/adam/pilot-final-readiness`.

Signed: Adam Issac, pilot launch owner — 2026-10-24; re-affirmed after the
production rehearsal leg 2026-10-25.
Code basis: production `readyz.git_sha` = `main` @ `0f311913` (schema 0.22.0,
migration head 0017); database ✓ queue ✓ 12 workers ✓ llm_mode `live` ✓
sandbox `vercel` ✓ github_app_configured ✓ webhook_secret ✓.

**Customer 1 is not cleared.** The production rehearsal passed every
leg through independent Verify, tenant isolation (34/34 → 404 on prod), RLS
(non-superuser), cancel, budget and scope-revoke drills — but verified fix
delivery failed closed (REHEARSAL_REPORT.md Leg 7, D1) and C9–C12 below are
open. GO requires every Yes-blocking row to be closed with evidence.

## Rehearsal evidence retained under this NO-GO decision

- Onboarding, push→assessment, monitoring, opt-outs, scope approval/revoke,
  cancel, budgets, audit and tenant membership checks are all implemented
  and the hosted path is verified live (45-case baseline + two connected
  production repos).
- The platform is honest under failure: transient failures stay FAILED,
  deferred work is queued-not-dropped, inconclusive findings are labelled.
- No claim in this package exceeds executed evidence.

## Outstanding launch conditions

Binding conditions — each maps to a documented gap. Customer 1 may not
start until every row marked Yes is done; C7–C8 are standing rules for the whole pilot.

| # | Condition | Blocking |
|---|---|---|
| C1 | Pilot scope held exactly as PILOT_SCOPE.md (Python, ≤2 repos, ingest caps, quota table) | Yes — scope discipline |
| C2 | Fix delivery restricted to `pull_request`/`manual`; `auto` never enabled for pilot orgs (watch audit log) | Yes |
| C3 | Defense Lab offered as recommendation-only/shadow; no control grants, no enforcement, simulation labelled | Yes |
| C4 | Deletion handled by an operator runbook with a ≤30-day SLA — `purge_project` merged (#535) and on prod — **DONE** | Yes |
| C4b | App connects as a dedicated `NOSUPERUSER NOBYPASSRLS` role. Today prod has one role, `postgres` (superuser + BYPASSRLS), and all 16 app connections use it, so the 0016 RLS policies are **inert for the app**. Follow DB_ROLE_MIGRATION.md, then re-run the prod tenant drill | Yes |
| C5 | Customer consent record (FIRST_FIVE_PLAN.md) signed before any repo access, covering: data storage, Anthropic processing, write-scope token, flagged-vs-validated, no auto-commit, no enforcement | Yes |
| C6 | Staging rehearsal (FIRST_FIVE_PLAN.md part 1) passes steps 1–10 on an unfamiliar repo + two orgs — local leg PASSED 2026-10-24; production leg 2026-10-25 PASSED except fix-PR delivery (C9) — **open until C9 closes and delivery is re-run** | Yes |
| C7 | Pilot claims track `main` only — anything not on the production `git_sha` is branch-only until merged and re-verified (#441 redaction-parse and #530 `jobs.last_error` redaction are merged and deployed) | Standing |
| C8 | Flagged ≠ validated is drilled at onboarding and in every report; Probe's four-template limit is always disclosed | Standing |
| C9 | Verified-patch delivery works when the diff contains credential-shaped fixture text (D1: `deliver_verified_patch` → `CONFLICT_STATE: the stored diff was redacted`). Fix through authorized trust-boundary review, then re-run the ledgerlite repair leg to an open (unmerged) PR | Yes |
| C10 | Per-project quota of 10/hour and 50/day shared by manual + automatic runs (owner target; code change in review), automatic runs opt-in, and prod `AUTOMATIC_ASSESSMENTS_PER_HOUR/_PER_DAY` lowered from the reported 60/500 | Yes |
| C10b | Pilot projects use `delivery_mode=pull_request`. The rehearsal project ran `auto`, which commits verified fixes directly to the default branch; D1 happened to block it | Yes |
| C11 | Sandbox capacity confirmed for the pilot. 19 assessments failed `HTTP 402 Hobby plan usage limit` between 10-20 and 10-23; none since, with about 9,800 sandbox-seconds on 10-24. Confirm which plan the sandbox team is on (D5) | Yes |
| C12 | Rotate the exposed Postgres password, Anthropic key and GitHub App key, then close Postgres public access. This is sequenced after C4b per DB_ROLE_MIGRATION.md (D6) | Yes |
| C13 | Railway runtime documents and checks the code-intelligence variables (`INTELLIGENCE_REPOSITORIES_FILE` + one persistence option) so a redeploy cannot reproduce the D3 snapshot failure | Before customer 2 |

## Documented exceptions (accepted for the pilot)

- No self-serve deletion or retention automation (R-03) — compensated by
  disclosure + operator SLA.
- RLS covers source-content tables only (`index_payloads`, `index_snapshots`);
  membership checks remain the boundary elsewhere (R-02) — verified on prod by
  the 34-probe ID-substitution drill.
- No repo-disconnect endpoint (R-04) — GitHub-side uninstall is the real
  cutoff; ops cleanup follows.
- No billing/metering — pilot is free; pricing remains a proposal.
- Strict all-seven-roles live success remains partially proven — IDOR
  chains complete end-to-end; broad CWE validation does not. Disclosed.
- Support is founder-led with response *targets*, not SLAs.

## Additional criteria for reconsidering the NO-GO decision

Rehearsal step failures; any cross-tenant access observed; deletion runbook
not delivered; the live eval materially regressing (re-run the 45-case set
if any of the open PRs merge first).
