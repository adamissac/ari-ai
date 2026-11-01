# Engineering execution plan (to first paying customer)

Date: 2026-10-31, `main` @ `4271503e`. Roles: **Claude** — product architecture, frontend,
integration, pilot tooling. **Devin** — backend, infra, orchestration, delegated implementation.
**Codex** — independent review, adversarial testing, release gate. **Adam** — production
operations, uptime, lifecycle (#723, #725). **Founder** — access, spend and product decisions.
Never two writers on one file set; each task is its own branch and PR.

Order: G1–G3 before Nov 2; G4–G7 for the pilot; G8 after the pricing decision.

### G1 — Restore production (S0)
- **Owner:** Railway operator (Adam / founder). **Depends on:** Railway access.
- **Scope:** redeploy backend and Postgres from `main` per `docs/yc/YC_DEPLOYMENT_RUNBOOK.md` (#744); redeploy frontend from the same SHA.
- **Acceptance:** `/readyz` 200; `/api/frontend-version` shows `backendReachable:true`, `sameCommit:true`.
- **Tests:** `scripts/ops/uptime_watch.py` (on #723) exits 0; sign-in round trip in a browser.
- **Customer impact:** without it nobody can use the hosted product.

### G2 — Land the reliability and safety PRs (S0)
- **Owner:** PR authors (#693, #694, #695 m-alan08/Devin; #723, #725 Adam). Codex certifies.
- **Depends on:** Codex audit of the union (`c9eedf7a` or later); R1 harness update for #725.
- **Scope:** merge in order #693 → #694 → #725 → #723 → #695; nothing else.
- **Acceptance:** all required CI green on each merge SHA; Codex GO recorded for the union.
- **Tests:** `make check`, `uv run mypy`, `make test`, `security-agents` suite, `deploy/evidence/restart_recovery.py` S1–S7.
- **Customer impact:** no credential leaks in diffs, no writes after disconnect, no duplicate PR reviews, crashed runs restart.

### G3 — One live hosted assessment (S0)
- **Owner:** Devin runs; founder approves a spend cap (F5).
- **Depends on:** G1, G2; a private company-owned copy of `examples/payments-lite/target` (DEMO_PREREQUISITES item 2).
- **Scope:** connect, setup, approve sandbox scope, run one assessment with a live model, approve the fix.
- **Acceptance:** assessment page shows Completed, live provider, ≥1 confirmed finding with executed evidence, a fix accepted by independent re-test; URL recorded in the handoff.
- **Tests:** `scripts/pilot/health_report.py --project <id>` reports `with_live_model_runs ≥ 1`, `security_confirmed ≥ 1`, `fix_verified ≥ 1`.
- **Customer impact:** first proof the product works end to end outside a laptop.

### G4 — Organization invites (S1)
- **Owner:** Devin (API, migration, tests), then Claude (Settings UI). **Depends on:** G2 merged (shared files).
- **Scope:** `org_invites` table; `POST/GET/DELETE /orgs/{id}/invites` (owner-only, audited, expiring); accept on GitHub login callback; members list with role change/remove.
- **Acceptance:** an owner invites `bob` as member; Bob signs in and sees the org's projects; a viewer cannot invite; an expired invite does nothing.
- **Tests:** API tests + a new case in `test_tenant_isolation_adversarial.py`; vitest for the UI; one Playwright spec.
- **Customer impact:** the second developer on a team can use Ari.

### G5 — Plan entitlements and usage view (S1)
- **Owner:** Devin (backend), Claude (UI). **Depends on:** founder decision F1.
- **Scope:** `org_plans` row; enforcement in repository connect and `check_project_quota`; `GET /orgs/{id}/usage` (repositories, completed assessments and model USD this period); Settings card.
- **Acceptance:** over-limit connect/start refuse with the existing quota error shape; usage equals the health report's numbers for the same period.
- **Tests:** quota tests extended; vitest; no payment provider involved.
- **Customer impact:** customers see what they use before anyone charges them.

### G6 — First-session UX (S1)
- **Owner:** Claude (#740), Devin (#696). **Depends on:** reviews.
- **Scope:** as in the PRs; then one terminology pass (audit P1-9/P1-10).
- **Acceptance:** CI green; Codex review threads resolved.
- **Tests:** `npm run lint/typecheck/test`; `tests/e2e/stack.py`.
- **Customer impact:** a failed or limited run is never read as a clean result; setup leads to a first run.

### G7 — Weekly pilot health report (S1, this PR)
- **Owner:** Claude (tool), founder (runs it weekly per design partner).
- **Scope:** `scripts/pilot/health_report.py` over existing membership-gated endpoints.
- **Acceptance:** per-org output only; no secrets printed; numbers from persisted records.
- **Tests:** `uv run pytest -q backend/tests/test_pilot_health_report.py` (3 tests, real API + PostgreSQL).
- **Customer impact:** measures time to first confirmed finding, false positives and verified fixes — the inputs for pricing and for the YC application, without inventing numbers.

### G8 — Stripe Checkout + Customer Portal (post-pilot)
- **Owner:** Devin. **Depends on:** F1, F2, G5, ≥3 paying design partners.
- **Scope:** one Checkout endpoint, one signed webhook updating `org_plans`, Portal link; no card data stored.
- **Acceptance:** test-mode subscription upgrades the plan; cancellation downgrades at period end; replayed webhooks are idempotent.
- **Tests:** webhook signature, ordering and replay tests with Stripe test fixtures.

## Coordination

- Each owner posts a `coordination/messages/` note when a G-task starts and finishes.
- Codex reviews every PR above; nothing merges red or unreviewed.
- Claude does not edit backend files for G4/G5/G8; it writes UI against the API once merged.
