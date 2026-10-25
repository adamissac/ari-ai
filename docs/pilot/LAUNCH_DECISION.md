# Launch decision — first five pilot customers

**Decision: CONDITIONAL GO**
Signed: Adam Issac, pilot launch owner — 2026-10-24; re-affirmed after the
production rehearsal leg 2026-10-25.
Code basis: production `readyz.git_sha` = `main` @ `0f311913` (schema 0.22.0,
migration head 0017); database ✓ queue ✓ 12 workers ✓ llm_mode `live` ✓
sandbox `vercel` ✓ github_app_configured ✓ webhook_secret ✓.

**Customer 1 is not yet recommended.** The production rehearsal passed every
leg through independent Verify, tenant isolation (34/34 → 404 on prod), RLS
(non-superuser), cancel, budget and scope-revoke drills — but verified fix
delivery failed closed (REHEARSAL_REPORT.md Leg 7, D1) and C9–C12 below are
open. GO requires every Yes-blocking row to be closed with evidence.

## Why GO is defensible for the narrow scope

- Onboarding, push→assessment, monitoring, opt-outs, scope approval/revoke,
  cancel, budgets, audit and tenant membership checks are all implemented
  and the hosted path is verified live (45-case baseline + two connected
  production repos).
- The platform is honest under failure: transient failures stay FAILED,
  deferred work is queued-not-dropped, inconclusive findings are labelled.
- No claim in this package exceeds executed evidence.

## Why not an unconditional GO

Binding conditions — each maps to a documented gap. Customer 1 may not
start until every row marked Yes is done; C7–C8 are standing rules for the whole pilot.

| # | Condition | Blocking |
|---|---|---|
| C1 | Pilot scope held exactly as PILOT_SCOPE.md (Python, ≤2 repos, ingest caps, quota table) | Yes — scope discipline |
| C2 | Fix delivery restricted to `pull_request`/`manual`; `auto` never enabled for pilot orgs (watch audit log) | Yes |
| C3 | Defense Lab offered as recommendation-only/shadow; no control grants, no enforcement, simulation labelled | Yes |
| C4 | Deletion handled by an operator runbook with a ≤30-day SLA — `purge_project` merged (#535) and on prod; RLS verified on prod with a non-superuser role — **DONE** | Yes |
| C5 | Customer consent record (FIRST_FIVE_PLAN.md) signed before any repo access, covering: data storage, Anthropic processing, write-scope token, flagged-vs-validated, no auto-commit, no enforcement | Yes |
| C6 | Staging rehearsal (FIRST_FIVE_PLAN.md part 1) passes steps 1–10 on an unfamiliar repo + two orgs — local leg PASSED 2026-10-24; production leg 2026-10-25 PASSED except fix-PR delivery (C9) — **open until C9 closes and delivery is re-run** | Yes |
| C7 | Pilot claims track `main` only — anything not on the production `git_sha` is branch-only until merged and re-verified (#441 redaction-parse and #530 `jobs.last_error` redaction are merged and deployed) | Standing |
| C8 | Flagged ≠ validated is drilled at onboarding and in every report; Probe's four-template limit is always disclosed | Standing |
| C9 | Verified-patch delivery works when the diff contains credential-shaped fixture text (D1: `deliver_verified_patch` → `CONFLICT_STATE: the stored diff was redacted`). Fix through authorized trust-boundary review, then re-run the ledgerlite repair leg to an open (unmerged) PR | Yes |
| C10 | Production automatic-assessment limits set to pilot values (`AUTOMATIC_ASSESSMENTS_PER_HOUR`, `_PER_DAY`, `AUTOMATIC_USD_PER_DAY`) — prod plateau of 60/h indicates an override above code defaults (D4) | Yes |
| C11 | Sandbox capacity: paid Vercel Sandbox plan or a hard cap below plan quota — 19 prior assessments failed `HTTP 402 Hobby plan usage limit` (D5) | Yes |
| C12 | Rotate the production Postgres password exposed during setup and disable Postgres public networking (D6) | Yes |
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

## What would change this to NO-GO

Rehearsal step failures; any cross-tenant access observed; deletion runbook
not delivered; the live eval materially regressing (re-run the 45-case set
if any of the open PRs merge first).
