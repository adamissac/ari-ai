# Tallybook: a realistic customer repository for testing Ari end to end

[`SrihithY/tallybook`](https://github.com/SrihithY/tallybook) (private) is a believable
seed-stage SaaS: a multi-tenant invoicing API for small agencies (FastAPI, SQLite, 30 tests,
CI). Its history contains the kinds of mistakes fast-moving teams ship, so one connected
repository exercises all three pillars. **This file is the answer key. Keep it out of the
Tallybook repository**: Ari indexes everything in a connected repository.

## Prerequisites

- PR [#263](https://github.com/adamissac/ari-ai/pull/263) merged and deployed. Without it,
  Probe/Verify checks import `payments_lite` and fail on every other repository.
- The hosted stack ready per [docs/prompts/11_HOSTED_E2E_RUN.md](../prompts/11_HOSTED_E2E_RUN.md)
  §0 (live LLM, GitHub App, webhook secret, `APP_ENV=production`, `SECURITY_SANDBOX=vercel`).
- The Ari GitHub App installed on `SrihithY/tallybook` (Install → Only select repositories).
- A second GitHub account for scope approval (the requester cannot approve).

## What is planted (answer key)

| Pillar | Where | What Ari should do | Introduced by |
|---|---|---|---|
| Security: IDOR (CWE-639) | `GET /invoices/{invoice_id}` (`tallybook/api/billing.py:get_invoice`) | Code intelligence flags "sibling routes enforce `require_tenant`"; Scout hypothesis; Probe `access_control.ownership` (maya→omar) **fails**; Patch adds `require_tenant`; Verify passes | `Invoice detail for the new dashboard…` (dropped the check) |
| Security / business logic (CWE-840) | `POST /credit-notes` | Probe `input_validation.bounds` on `create_credit_note` **fails** (credited 1201.00 > 1200.00); Patch compares the running sum | `Billing: invoices…` (checks each note alone) |
| Functional (reviewer) | `tallybook/pricing.py:compute_totals` | Reviewer cites docs/billing-rules.md + docstring ("tax must be calculated on the discounted subtotal"), generates a failing test (10 h × $120, $200 discount, 10 % tax → expect tax 100.00 / total 1100.00, gets 120.00 / 1120.00), proposes a repair | `Itemized tax per line…` |

**Lookalikes that must NOT be reported** (precision):
`GET /clients/{id}`, `GET /payments/{id}`, `GET /credit-notes/{id}` and
`GET /invoices/{id}/payments` all call `require_tenant`; `POST /payments` enforces its
bound (`record_payment` bounds check passes); `PATCH /clients/{id}` builds SQL column
names only from Pydantic field names (not injectable).

**Open PR #1 (monitoring leg):** `CSV export of an invoice for accountants` adds
`GET /invoices/{invoice_id}/export.csv` without `require_tenant` (a new IDOR) and adds the
route to `build_recipe.json`. Merging it is a signed push → monitoring event →
push-triggered reassessment that reviews the diff.

### Verified locally before handoff (2026-10-17)

- Tallybook: 30 tests and ruff pass on every commit; the flaws reproduce
  (other agency reads `inv_1001` → 200; credits reach 1201.00; tax 120.00 vs 100.00).
- Ari's real check templates (branch of #263, local-process driver):
  ownership `invoice_detail` **fails**; `invoice_payments`, `client_detail`,
  `payment_detail`, `credit_note_detail` hold; bounds `create_credit_note` **fails** for
  both identities; `record_payment` holds for both.
- Code intelligence at HEAD: 15 entry points, 137 expectations; exactly one sibling
  ownership flag, on `GET /invoices/{invoice_id}`; tenancy, payment/credit caps and
  discount-before-tax rules extracted from docstrings and docs.
- Runtime ingest (real backend endpoint and scorer, test database): 48 normal hourly windows
  then the attacks. Enumeration scores 1.0 on `GET /invoices/{invoice_id}` (rate z≈11,
  error ratio +0.48); credential stuffing scores 1.0 on `GET /me` (auth-failure ratio
  +0.62). Normal traffic produced one borderline alert (z=3.1) in 48 hours.

Not verified: a live LLM run on Tallybook (not authorized; costs money) and the hosted
Vercel sandbox.

## Demo run

1. **Connect.** Sign in at https://ari-ai-lake.vercel.app → Connect → `SrihithY/tallybook`
   → create project "Tallybook".
2. **Scope.** Request a sandbox scope: target the repository, recipe `build_recipe.json`,
   categories `access_control.ownership` and `input_validation.bounds`, expiry ≤ 24 h.
   Second account approves.
3. **Assess HEAD of `main`** (`Itemized tax per line…`). Watch the timeline: reviewer, then
   Scout → Probe → Trace → Diagnose → Patch → Verify → Fortify. Approve remediations when
   asked (second account). Expect the three planted findings above and no lookalikes.
4. **24-hour monitoring.**
   - Create an ingest token. There is no UI button yet; in the browser console on the
     Ari site while signed in as a project owner:
     ```js
     const me = await (await fetch('/api/v1/me')).json();
     const r = await fetch('/api/v1/projects/<prj_id>/ingest-tokens',
       { method: 'POST', headers: { 'X-CSRF-Token': me.csrf_token } });
     (await r.json()).token   // shown once
     ```
   - In Tallybook → Settings → Secrets and variables → Actions: secret `ARI_INGEST_TOKEN`;
     variables `ARI_API_URL=https://ari-ai-production-76d4.up.railway.app`,
     `ARI_PROJECT_ID=<prj_id>`.
   - Actions → runtime-signals → Run workflow, `backfill: 12` (baseline), then once with
     `scenario: enumeration` to see an anomaly immediately. After that it runs hourly by
     itself: enumeration at 03:00 UTC and credential stuffing at 15:00 UTC appear in the
     project's monitoring feed as `simulated` `log_anomaly` events, linked to the open
     finding on `GET /invoices/{invoice_id}`. These never start assessments (no LLM cost).
5. **Push-triggered reassessment.** Merge Tallybook PR #1. The signed push creates a
   monitoring event (redelivery is deduplicated) and a reassessment of the diff that should
   find the new export IDOR. This spends up to the project's monitoring budget ($3 by
   default); cancel it if that spend is not approved.

## Costs

- LLM: step 3 is one full assessment (capped by `LLM_MAX_USD_PER_ASSESSMENT`, $10 default);
  step 5 is one monitoring run (≤ $3). Steps 1, 2 and 4 cost nothing.
- GitHub Actions on a private repo: CI ≈ 1 min per push; runtime-signals ≈ 1 min per hour
  once configured (~730 min/month of the 2,000 free). It is skipped until
  `ARI_PROJECT_ID` is set.

## Known limitations surfaced by this repository

- The runtime scorer compares each route only with its last 12 windows and has no
  daily seasonality, so a sharp day/night swing alerts on rate alone. The simulator keeps
  the daily curve gentle (±10 %).
- Only two reviewed check templates exist (ownership on GET routes, amount bounds on a
  POST create route), so Probe can prove only those classes; other issues remain
  reviewer/LLM findings without a sandboxed proof.
- No UI to create runtime ingest tokens yet (API only).
