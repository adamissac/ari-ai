# Launch decision — first five pilot customers

**Decision: NO-GO**

## Blocking conditions (2026-10-25)

- Leg 8 proved production PR delivery with #2 and #4, but C9 remains open: no independent security review or owner approval of #587 is recorded on GitHub, the owner has not decided approval semantics, and no owner-witnessed Ari PR remains open for personal review and merge or closure.
- The Leg 7 production assessments were started by the synthetic account `rehearsal-alice`, not a real customer identity.
- The production application connects to PostgreSQL as a superuser with BYPASSRLS, so row-level security is inert.
- No genuine user has completed the intended end-to-end flow through the website.

Evidence: `docs/pilot/PILOT_FINAL_READINESS.md` on `docs/adam/pilot-final-readiness`.

Signed: Adam Issac, pilot launch owner — 2026-10-24; re-affirmed after the
production rehearsal leg 2026-10-25.
Code basis: Leg 8 ran production `497372ff` (#587); Run 2 used `95e90861`
(including #599). Final observed `/readyz`: ready, 24 workers, 0 queued.

**Customer 1 is not cleared.** Leg 8 proved the production PR-delivery
mechanism, but C9 remains open and C6 still requires the hosted browser journey
with real GitHub sign-in and unaided onboarding. GO requires every
Yes-blocking row to be closed with evidence.

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
| C6 | FIRST_FIVE_PLAN.md part 1 is open until the hosted browser journey passes with real GitHub sign-in and unaided onboarding; the API-only rehearsal with server-created accounts does not close it | Yes |
| C7 | Pilot claims track `main` only — anything not on the production `git_sha` is branch-only until merged and re-verified (#441 redaction-parse and #530 `jobs.last_error` redaction are merged and deployed) | Standing |
| C8 | Flagged ≠ validated is drilled at onboarding and in every report; Probe's four-template limit is always disclosed | Standing |
| C9 | PR delivery was proven on production (#2 and #4), but closure remains open until (a) independent security review and owner approval of #587 are recorded (none are on GitHub), (b) the owner decides approval semantics (standing authorization rechecked at delivery plus a human merging the PR; branch protection is unavailable on free private repos), and (c) one Ari-delivered PR is left open for the owner to review and personally merge or close. During the pilot, no agent may merge or close an Ari fix PR on a customer repo; only the customer's human may | Yes |
| C10 | **DONE:** shared per-project limits are 10/hour and 50/day across manual + automatic assessments, with automatic runs opt-in; final verified Railway values are `PROJECT_ASSESSMENTS_PER_HOUR=10`, `PROJECT_ASSESSMENTS_PER_DAY=50`, and `ASSESSMENTS_USD_PER_DAY=50` | Yes |
| C10b | Pilot projects must use `delivery_mode=pull_request`; the rehearsal project was switched from `auto` to `pull_request` before Leg 8 via an audited PATCH. This does not close C9's owner-review and human merge/close gates | Yes |
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
