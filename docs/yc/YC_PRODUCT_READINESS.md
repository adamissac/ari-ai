# Ari AI customer-readiness assessment (YC W27)

Date: 2026-10-31. Base: `main` @ `4271503e`. Author lane: product architecture / execution
(Claude). Release GO/NO-GO is Codex's call ([#739](https://github.com/adamissac/ari-ai/pull/739));
backend reliability evidence is Devin's ([#744](https://github.com/adamissac/ari-ai/pull/744)).
This document does not grant or change either.

**Evidence words.** *Verified (local)*: executed on the local real stack (FastAPI + PostgreSQL +
worker + Next, model replies scripted unless stated). *Verified (prod)*: observed on the hosted
deployment. *Not verified*: not executed. No readiness percentages; no customer has used Ari.

**Severity.** **S0** blocks any controlled pilot. **S1** blocks a paid or self-serve launch.
**S2** post-launch improvement.

Related: [MVP_SCOPE](../planning/MVP_SCOPE.md) · [LAUNCH_BLOCKERS](LAUNCH_BLOCKERS.md) ·
[SAAS_ARCHITECTURE](SAAS_ARCHITECTURE.md) · [CUSTOMER_ONBOARDING](../pilot/CUSTOMER_ONBOARDING.md) ·
[ENGINEERING_EXECUTION_PLAN](ENGINEERING_EXECUTION_PLAN.md).

## Technical audit in one paragraph

The core loop is real code with real tests: GitHub OAuth sign-in, GitHub App installation,
repository connect, an 8-question setup, an owner-approved sandbox scope, an orchestrated
assessment (reviewer + Scout → Probe → Trace → Diagnose → Patch → Verify → Fortify), executed
validation checks, human approval before any fix is built, independent re-test, and fix
delivery as a PR or in-app proposal. Each of these is exercised by the backend suites (879
passed on `9437e217`, Devin) and by the Playwright journey on the real local stack (28 passed,
this lane, scripted model replies). **What has never been observed** is the same loop on the
hosted deployment with a live model against a real repository, and the hosted backend is down
right now (`/healthz` → Railway 404 at 2026-10-31T17:09Z, this session). Validation by executed
checks exists only for **Python HTTP services**; JS/TS repositories get a functional review but
no validated security findings. There is no team workspace, billing, or product analytics.

## A. Current product capabilities

| Capability | State | Evidence |
|---|---|---|
| Sign in with GitHub; personal organization per login | Implemented | `backend/backend/api/auth.py:127`; e2e `onboarding` spec (local) |
| GitHub App install, repository list, connect, disconnect, reconnect | Implemented | `github_repos.py`, #679; e2e (local) |
| Build-recipe PR on connect (`ari/build-recipe`) | Implemented | `recipes.py`; not observed on hosted |
| Setup (8 questions), sandbox scope with owner approval and expiry | Implemented | `routes.py` scopes; unit + e2e (local) |
| Manual assessment of a pinned commit, live progress, cancel | Implemented | e2e `journey` (local) |
| Seven security agents + reviewer as separate tool-use loops | Implemented | `security-agents/` suites; live run never recorded on hosted |
| Executed validation of security hypotheses | **Python HTTP services only** | `docs/pilot/PILOT_SCOPE.md:10-12` |
| JS/TS repositories | Functional review only; no validated security findings | #681 |
| Human approval gate before Patch; independent Verify | Implemented | e2e `honesty`, `journey` (local) |
| Fix delivery: in-app proposal or PR (auto-commit exists, not for pilots) | Implemented | `delivery.py`, `auto_commits.py` |
| Automatic review of pushes (per-repo switch, default OFF) | Implemented, rate-limited | `RAILWAY_AND_GITHUB_APP.md` §per-commit |
| Per-assessment usage (tokens, USD, sandbox seconds) and budget caps | Implemented | `shared/shared/tenancy.py:19-33`, `quota.py` |
| Project quota (10/h, 50/day) + $50/day global spend cap | Implemented | `quota.py`; LAUNCH_DECISION C10 |
| Tenant isolation between organizations | Implemented, adversarially tested | `backend/tests/test_tenant_isolation_adversarial.py` |
| Outcome / coverage honesty on assessment pages | In review | PR #740 (this lane) |
| Pilot health report (activation, findings, fixes, spend) | New in this PR | `scripts/pilot/health_report.py`, 3 tests (local) |
| Defense Lab / RL recommendations | Recommendation-only research surface | Not part of the commercial MVP |
| Team workspaces, invites | **Missing** | No membership API exists |
| Billing, entitlements, trial | **Missing** | Pricing page states nothing can be purchased |

## B. Critical launch blockers

| # | Sev | Blocker | Owner |
|---|---|---|---|
| B1 | S0 | Hosted backend is down (Railway "Application not found"); frontend reports `backendReachable:false` and serves `c03a5501`, behind `main` | Railway operator (Adam / founder) per `docs/yc/YC_DEPLOYMENT_RUNBOOK.md` (#744) |
| B2 | S0 | No live hosted assessment has ever completed against a company-owned repository | Devin (run) + founder (approve spend) |
| B3 | S0 | Release-gate safety fixes are unmerged and #693×#694 conflict: credential-literal redaction (#694), release checker accepting empty/skipped CI (#695), lost-worker restart (#725) | PR owners; Codex certifies the union |
| B4 | S1 | No team workspace: a second developer cannot join the first developer's organization | See G4 |
| B5 | S1 | Validation only for Python HTTP services; most 2–30-person startups ship TypeScript | Founder decision (F3) |
| B6 | S1 | No way to take payment or enforce a plan | See SAAS_ARCHITECTURE |

## C. Security and reliability blockers

From Codex #739 and Devin #744, not re-derived here:

| # | Sev | Issue | Status |
|---|---|---|---|
| C1 | S0 | Credential literals survive diff redaction (Python strings, triple-quoted, unquoted YAML) | Fixed on #694, unmerged |
| C2 | S0 | Release checker treats zero/skipped checks as PASS; `main` protection not visible (404) | Fixed on #695, unmerged; admin must confirm branch protection |
| C3 | S0 | Disconnect could race an in-flight GitHub write; duplicate PR reviews on 5xx | Fixed on #693/#694, unmerged |
| C4 | S1 | Worker crash fails the assessment with no recovery | Fixed on #725, unmerged; evidence harness R1 needs update |
| C5 | S1 | Outages are not detected (10-28 outage lasted ~2 days unnoticed) | #723 watchdog, unmerged; probes `/healthz` only (W1) |
| C6 | S1 | `register_verified_regression` jobs end dead with `SNAPSHOT_NOT_READY` in e2e logs | Unconfirmed impact; handoff in `docs/reviews/2026-10-31-first-customer-audit/` |
| C7 | S1 | Data deletion is operator-run (≤30 days), not self-serve; retention indefinite until request | Documented in `docs/pilot/DATA_HANDLING.md`; acceptable for pilot with consent |
| C8 | S2 | Sandbox in production is Vercel Sandbox microVM; capacity/cost per assessment not measured on hosted | Measure on B2's run |

## D. Missing customer-facing functionality

| # | Sev | Missing | Why it matters |
|---|---|---|---|
| D1 | S1 | Invite a teammate to an organization (roles already exist: owner/member/viewer) | ICP is a team, not a person |
| D2 | S1 | Plan, usage this period, and limit shown to the customer | Needed before charging; `usage` already persisted |
| D3 | S1 | Self-serve data deletion request (even a button that files a ticket) | Trust; today it is email |
| D4 | S2 | Notifications (email/Slack) when a run finishes or a fix awaits approval | Approvals go stale silently |
| D5 | S2 | One glossary pass (check / assessment / review; fix-delivery labels) | Audit P1-9, after #696 |

## E. Technical debt that can be deferred

Defense Lab, RL policy serving and first-responder modes (keep recommendation-only, out of the
commercial MVP); the many `docs/status` no-op PRs (#702–#743) (close, they hide real PRs);
duplicate "Analyze this commit" links; coarse coverage record (derived from agent runs);
auto-commit delivery mode (keep disabled for pilots); R2 lost-segment budget under-count.

## F. Recommended minimum commercial product

See [MVP_SCOPE](../planning/MVP_SCOPE.md). In short: **one GitHub org, Python HTTP service
repositories, manual and opt-in push-triggered assessments, validated findings with executed
evidence, human-approved fixes delivered as pull requests, independent re-test, and a weekly
health report.** No auto-commit, no Defense Lab, no RL, no enterprise features.

## G. Highest-impact engineering tasks

Ranked; full owner/scope/acceptance in [ENGINEERING_EXECUTION_PLAN](ENGINEERING_EXECUTION_PLAN.md).

1. **G1 (S0)** Redeploy production from `main`, verify `/readyz` and frontend `sameCommit:true`.
2. **G2 (S0)** Merge #693 → #694 → #725 → #723 → #695 after Codex certifies the union.
3. **G3 (S0)** One bounded live assessment on a company-owned staging repo on the hosted stack; record its URL.
4. **G4 (S1)** Organization invites by GitHub login (owner-only, audited).
5. **G5 (S1)** Plan entitlement row + usage-this-period view (no payment provider yet).
6. **G6 (S1)** Merge #740 and #696 (first-session UX, honest outcomes).
7. **G7 (S1)** Pilot health report runs weekly per design partner (this PR).

## H. Deployment and operational requirements

- Backend + PostgreSQL on Railway, frontend on Vercel, sandboxes on Vercel Sandbox
  (`docs/deploy/RAILWAY_AND_GITHUB_APP.md`). Someone besides one person must hold Railway access.
- Deploy backend and frontend from the same `main` SHA; check `/api/frontend-version`.
- Uptime alerting on `/readyz` (not only `/healthz`) with a named on-call during the pilot.
- Postgres backups with one tested restore (`docs/deploy/POSTGRES_STORAGE.md`).
- Anthropic spend limit at the account level in addition to the $50/day app cap.
- Branch protection on `main` requiring the real CI jobs (C2).

## I. Proposed first-customer onboarding workflow

See [CUSTOMER_ONBOARDING](../pilot/CUSTOMER_ONBOARDING.md). Owner-attended for the first
session; target is a confirmed finding with evidence in the first session, and the health
report measures whether that happened.

## J. Recommended next steps before November 2

1. Founder/operator restores production (G1). Without it there is no hosted demo; use the local
   fallback in `docs/demo/yc-w27/DEMO_RUNBOOK.md` and say the model replies are scripted.
2. Owners merge the reliability PRs in the order in #744 once Codex certifies them (G2).
3. Run G3 with an explicit spend cap; bookmark the assessment; run the health report on it.
4. Merge #740 and #696 after review.
5. Do **not** start billing code before the founder decisions below.

## Founder decisions required

| # | Decision | Recommendation |
|---|---|---|
| F1 | Pricing unit: per repository, per seat, or per assessment | Per connected repository with an included assessment allowance (SAAS_ARCHITECTURE §pricing) |
| F2 | Pilot paid or free | Paid design-partner pilot, invoiced manually, 3–5 teams |
| F3 | Pilot ICP language | Python HTTP services for the pilot; JS/TS validation is the next build, not a pre-launch one |
| F4 | Who holds production access and on-call | Two people with Railway + Vercel access |
| F5 | Spend for live verification runs | Approve a fixed budget (e.g. $25) for G3 |
| F6 | Third-party product analytics | None for the pilot; first-party report only |
