# Minimal SaaS architecture for Ari

Status: **recommendation, not implemented.** Nothing here is built except where a row says
*exists*. Pricing and the payment provider are founder decisions (F1, F2 in
[YC_PRODUCT_READINESS](YC_PRODUCT_READINESS.md)). Base: `main` @ `4271503e`.

Goal: launch simple pricing, learn willingness to pay from 3–5 design partners, and add as
little infrastructure as possible that someone must maintain.

## What exists to build on

| Building block | Exists | Where |
|---|---|---|
| Organization, users, memberships with roles owner / member / viewer | Yes | `backend/backend/db.py:39-67` |
| Every project, repository, assessment, finding scoped to an org; membership checked per request | Yes | `api/deps.py` `require_project`; `test_tenant_isolation_adversarial.py` |
| Per-assessment usage: tokens, USD, sandbox seconds, LLM / tool calls | Yes | `shared/shared/tenancy.py:25-33`, persisted on the assessment doc |
| One choke point for starting assessments (manual and automatic) | Yes | `backend/backend/quota.py` `check_project_quota` |
| Per-project hourly/daily limits, global $/day cap, per-assessment budget clamped to operator caps | Yes | `quota.py`, `settings.py` |
| Hash-chained audit log | Yes | `audit_events`, `GET /audit` |
| Invitations / joining another user's organization | **No** | Only the personal org is created at first login (`auth.py:127`) |
| Plan, entitlement, subscription, checkout | **No** | — |
| Product analytics | **No** | — |

## 1. Organizations and workspaces

**Recommendation: keep the existing organization as the workspace; add owner invites by GitHub
login.** One table (`org_invites`: org_id, github_login, role, invited_by, expires_at,
accepted_at). When the invited login signs in, the callback inserts the membership. Owner-only,
audited, expiring.

Alternative considered: derive membership from GitHub organization membership. Less to type for
the customer, but it needs the `members:read` org permission (a broader App permission request)
and silently grants access when someone joins the customer's GitHub org. Revisit after the pilot.

## 2. GitHub App installation and permissions

Exists and is sufficient: Contents read/write, Pull requests read/write, Metadata read; push
webhooks, HMAC-verified; read tokens and repository-pinned write tokens minted per call and never
persisted (`docs/pilot/CUSTOMER_ONBOARDING.md` step 2). No permission change is needed for the
MVP. Write access is only used for approved fix delivery and the build-recipe PR; say so in the
install flow (PR #740 adds that copy to the Organizations page).

## 3. Multi-tenant isolation

Exists: shared database, row-level scoping by `org_id` through projects, enforced in request
handlers and covered by adversarial tests. Recommendation for the pilot: **no schema-per-tenant
or database-per-tenant**. Two additions before a paid launch:

- Run `test_tenant_isolation_adversarial.py` in required CI (it already runs in `backend-tests`)
  and add a case for every new org-scoped endpoint (invites, plan).
- Keep the cross-customer roll-up outside the product (the health report is per-org by
  construction: it uses one owner's session).

## 4. Usage measurement

Exists per assessment. Missing: a per-org, per-billing-period sum. Recommendation: compute it on
read (`SUM` over the org's assessments in the period); no counters, no event pipeline. Meter
three numbers: **connected repositories**, **completed full assessments**, **model USD** (cost
control, not billed). At pilot scale a query over `assessments` is enough.

## 5. Subscription entitlements

One row per organization (`org_plans`: plan, repo_limit, assessments_per_month,
period_start, status, provider_customer_id nullable). Enforce in exactly two places that
already exist:

- repository connect (`POST /projects/{id}/repositories`): refuse above `repo_limit`;
- `check_project_quota`: refuse above `assessments_per_month`, with the same error shape the
  hourly/daily limits use, so the frontend's existing quota message applies.

Pilot organizations get their row set by an operator. No feature flags per plan: every plan has
every feature, differentiated only by limits (matches the deck's proposal).

## 6. Billing-provider integration

**Phase 1 (pilot, now): no integration.** Invoice design partners manually (Stripe Invoicing or
Payment Links from the dashboard, no code). Operator sets `org_plans`.

**Phase 2 (after ≥3 paying teams): Stripe Checkout + Customer Portal.** One endpoint creates a
Checkout session; one signed webhook (`checkout.session.completed`,
`customer.subscription.updated|deleted`) updates `org_plans`. Stripe hosts payment pages,
invoices, tax and cancellation; Ari stores no card data. No usage-based billing API: overage is
handled by a hard limit plus an upgrade link.

| Option | Maintenance | Risk | When |
|---|---|---|---|
| Manual invoices + operator-set plan | Lowest | Human error on limits | Pilot |
| Stripe Checkout + Portal + 1 webhook | Low | Webhook replay/ordering (use event id idempotency, store last event time) | First self-serve customers |
| Stripe metered billing | Medium | Disputes over counted usage; needs a trustworthy meter | Only if per-assessment pricing wins |
| Merchant of record (Paddle / Lemon Squeezy) | Low | Fees; fewer B2B invoice options | If sales tax handling becomes the blocker |

## 7. Customer onboarding and trials

Trial = the free tier of the same plan model: 1 repository, a small monthly assessment
allowance, same features. No time-limited trial machinery. The onboarding path is
[CUSTOMER_ONBOARDING](../pilot/CUSTOMER_ONBOARDING.md); the metric is time to first confirmed
finding.

## 8. Basic product analytics

**Recommendation: no third-party analytics during the pilot.** Customer code and finding titles
are sensitive, and an analytics SDK in the console is one more processor to disclose. Use the
first-party activation report (`scripts/pilot/health_report.py`, this PR): time from project
creation to first assessment, first completed assessment, first confirmed finding and first
verified fix; findings confirmed vs ruled out; fixes written vs verified; stale approvals;
spend per completed assessment. Add a privacy-reviewed page-level tool later if funnel drop-off
inside the UI becomes the question.

## Pricing recommendation (founder decision F1)

Price per **connected repository** with an included monthly assessment allowance. Repositories
are what a 2–30-developer team counts, they map to an existing enforcement point, and they avoid
per-seat friction for a tool whose value is per codebase. Treat the numbers as hypotheses to test
with design partners. The deck proposes $99 / $299 / $799; `frontend/app/pricing` proposes plans
by assessments and source lines. Pick one before showing either to a customer.

## Build order

1. Invites (G4) — needed by every team, paid or not.
2. `org_plans` + usage-this-period view + enforcement (G5).
3. Stripe Checkout/Portal — only after F1/F2 and ≥3 paying design partners.
