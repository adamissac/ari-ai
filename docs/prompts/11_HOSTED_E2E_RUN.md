# Prompt: one real hosted end-to-end assessment (issue #244, P0 "hosted integration")

Paste this to an agent (or follow it by hand) **only after the product owner approves the
spend**. It drives one real assessment through the hosted product with live Claude calls.
Everything else in it is read-only verification and evidence collection.

---

You are verifying the hosted Ari product end to end, once, on the owned sandbox target.
Owner-approved budget: **$`<CAP>`** (set it below; stop if the assessment would exceed it).

## Boundaries (non-negotiable)

- Target **only** the team-owned `payments-lite` repository (or another repository the
  owner names in writing) through the installed GitHub App. Never a third-party repository,
  never production systems, never a URL outside the authorized scope.
- Never print, paste, commit or screenshot a secret (API keys, App private key, webhook
  secret, installation tokens, session cookies). Redact if one appears in a log.
- Do not change hosting configuration (Railway/Vercel variables, App settings) yourself.
  If something is missing, stop and report exactly which setting.
- One run. If it fails, collect evidence and stop; a retry needs fresh owner approval.

## 0. Preflight (read-only)

1. `GET https://ari-ai-production-76d4.up.railway.app/readyz` must report
   `database: true, queue: true, llm_mode: "live", github_app_configured: true,
   webhook_secret_configured: true`.
2. Confirm with the owner (not by reading secrets) that Railway has `APP_ENV=production`,
   `SECURITY_SANDBOX=vercel` and the Vercel Sandbox credentials. Without them the reviewer
   and security sandboxes **fail closed** (#246) and the run will stop at the first test.
3. Confirm Vercel has `BACKEND_ORIGIN` set and `NEXT_PUBLIC_DEMO_ONLY` removed, so
   https://ari-ai-lake.vercel.app/projects is the real console, not `/demo`.
4. Two GitHub accounts with access (two-person scope approval): requester and approver.

## 1. Journey (through the UI, as a user would)

1. Sign in at https://ari-ai-lake.vercel.app with GitHub (account A).
2. Connect: choose the organization → `payments-lite` → note the default branch.
3. Create a project; the repository appears via the App installation.
4. Request a sandbox scope (target = the repository, `build_recipe.json`, categories
   `access_control.ownership` and `input_validation.bounds`, expiry ≤ 24 h).
5. Account B approves the scope (the requester cannot).
6. Pick a specific commit from the commit list; record its full 40-char SHA.
7. Start the assessment. Watch the live timeline (SSE).
8. When it pauses at **Human approval required**, account B approves each remediation
   (security fix and, if present, the reviewer's functional repair).
9. Wait for a terminal state.

## 2. Evidence to collect (from the API with account A's session, not screenshots alone)

- `GET /api/v1/assessments/{id}`: `state`, `commit_sha`, `repo_id`, `usage` (tokens, usd,
  llm_calls, tool_calls, sandbox_seconds).
- `agent_runs`: for every role (reviewer, scout, probe, trace, diagnose, patch, verify,
  fortify): `status`, `provider_mode` (must be `live`, except the functional Verify which is
  `none` by design), `model_id`, `llm_calls`, `tool_calls`.
- Findings: each security finding's `status` + `history`; patches with the independent
  `VerificationResult` (verdict, five checks, produced_by_run_id ≠ the patch's run).
- `GET /api/v1/assessments/{id}/rules-of-engagement` (must return the issued RoE).
- `GET /api/v1/assessments/{id}/events/log` paged with `next_cursor` to the end; the last
  event is the terminal state.
- `GET /api/v1/audit?project_id=…`: `chain_verified: true`.
- The sandbox driver recorded in run evidence (must be the Vercel microVM, not
  local-process).

## 3. Monitoring leg (no extra model spend unless it triggers an assessment)

Push a behaviour-neutral commit to `payments-lite` (e.g. a comment) and confirm:
a monitoring event appears for the signed delivery, redelivery is deduplicated, and a
reassessment is created. Cancel any reassessment it starts unless the owner approved a
second run's spend.

## 4. Report

Post one comment on issue #244 (and a `coordination/messages/` file) with: date/time,
main commit deployed, assessment id, commit SHA, per-role table (status, provider, model,
calls, tools, cost), total cost vs cap, verdicts, RoE id, audit chain result, monitoring
event id, and **explicit limitations** (anything skipped, failed, or simulated). Do not
tick a checkbox unless every acceptance item above has evidence.
