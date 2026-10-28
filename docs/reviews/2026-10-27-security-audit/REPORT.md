# Security audit — upstream main @ c03a5501 (2026-10-27)

Scope: tenant/repo isolation, GitHub App permissions and revocation, OAuth/session,
authorization before provider calls, secret exposure, worker cancellation and disconnect
races, webhook authenticity/replay/idempotency, prompt injection, sandbox isolation.
Status labels: **Reproduced** (failing controlled test on main), **Reviewed** (source read,
existing tests pass, no new repro), **Unverified** (not exercised here).

## Findings, by severity

### H1 — High — Disconnect does not stop a queued or in-flight verified-fix delivery (Reproduced, fixed)
`deliver_verified_patch` jobs carry only `assessment_id`/`verification_id`, so the
disconnect kill-switch (`POST /repositories/{id}/disconnect`, which cancels jobs by
`payload.repo_id`/snapshot/mapping) never reaches them. The handler only checked
`installation_id`, which disconnect deliberately keeps. Result: after an owner disconnects,
Ari still mints a write-scoped installation token and pushes to the default branch
(`auto`) or opens a fix PR (`pull_request`).
Repro: `test_disconnect_stops_a_queued_verified_fix_delivery` failed on main with
`FakeApp.calls == [('push', 'main', True)]`.
Fix (`backend/backend/delivery.py`): skip delivery (`delivery.skipped`, reason
`repository is disconnected`) when `repositories.disconnected_at` is set, and re-check it
before minting the token, before each `push_patch`, and before `open_pull_request`, so a
disconnect during the slow fetch/tip-check window also stops the write.

### M1 — Medium — Disconnect does not stop a queued PR review comment (Reproduced, fixed)
`post_pr_review` has the same payload gap and only checked `installation_id`, so findings
were still posted to the pull request after disconnect.
Fix (`backend/backend/auto_commits.py`): no-op when `disconnected_at` is set.

### H2 — High — Check-then-write window; installation detachment not re-checked; build-recipe writes unguarded (Reproduced, fixed; Codex re-review 2026-10-28)
Codex's independent review of #694 found three gaps left by H1/M1:
1. The disconnect check ran in its own transaction, then the GitHub write followed. A
   disconnect landing between the two (e.g. during `fetch_commit`, or between
   `post_pr_review`'s read and its POST) still let the push / review reach GitHub.
2. Only `disconnected_at` was consulted. When GitHub detached the App installation
   (`installation.deleted`, `installation_repositories.removed`, `repository.deleted` →
   `installations._detach` clears `repositories.installation_id`), the running job kept
   using the token it had already minted and wrote anyway.
3. `propose_build_recipe` checked the connection once at job start, then spent the slow
   analysis/draft phase without re-checking before the write token, `push_patch`, or
   `open_pull_request`.
Repro (all five fail on `ea3d58e6`, pass now):
`test_installation_detached_during_delivery_stops_before_the_github_write`
(`FakeApp.calls == [('push', 'main', True)]`),
`test_disconnect_right_before_the_pr_review_post_stops_it` and
`test_installation_detached_before_the_pr_review_post_stops_it` (review POSTed),
`test_disconnect_during_recipe_drafting_stops_the_push_and_pr` and
`test_installation_detached_during_recipe_drafting_stops_the_push_and_pr` (recipe PR opened
and `ari/build-recipe` pushed to the remote).
Fix (`backend/backend/connection_guard.py`): `require_connected(repo_id, installation_id)`
re-reads `disconnected_at` and `installation_id` and raises `RepositoryDetached` with the
reason when the repo is disconnected, detached, or re-bound to another installation.
`deliver_verified_patch` and `propose_build_recipe` call it immediately before the write
token, each push, and the pull request (recording `delivery.skipped` / `recipe.skipped`
with the reason); `post_pr_review` calls `connection_problem` immediately before the POST.
The read is still not atomic with the GitHub call itself — a disconnect committed while the
HTTP request is in flight cannot be recalled — but the window is now the single network
call rather than the whole job, and `assess_commit` already serialises its scheduling
under a row lock. Not changed: `installations.py` (detachment itself was complete; what
was missing was that running writers never looked at it).

### P2 — N8 password-literal leakage: historical forms fixed; broader literal forms remain (Reviewed, not fixed)
On current main the reported N8 forms (quoted mapping keys, subscripts, annotated
assignments) and the N9 statement-boundary regression are fixed:
`test_rc4_n8_artifact_disclosure.py` + `test_rc4_n9_statement_boundaries.py` pass (7).
A wider probe found `redact_code` still leaves literals under sensitive names in
triple-quoted, f-/b-/r-prefixed strings and YAML/`.env`-style values. Impact is limited:
the diff artifact is only readable by project members (outsiders get 404); delivery
ships the sealed, Verify-bound diff and refuses high-confidence secrets; key-shaped tokens
(GitHub, AWS, Anthropic, Slack, Stripe, private keys, DSN passwords) are still redacted.
Recommended follow-up: extend `_CODE_KV_PATTERN` literal prefixes and add YAML/env forms.

### P3 — Legacy (non-per-commit) push path does not bind payload installation to the repo (Reviewed)
`pipeline.process_github_delivery` resolves the repo by `full_name` and uses the stored
`installation_id` for compare calls; the payload's installation is not compared (the
per-commit path in `auto_commits.schedule` does compare). Requires a valid webhook HMAC, and
provider calls use the repo's own installation, so no cross-tenant read was found.

## Reviewed with no finding
- Webhooks: bounded body → HMAC-SHA256 over raw bytes (`hmac.compare_digest`) → header
  shape checks → JSON → `ON CONFLICT DO NOTHING` delivery-id dedupe; placeholder secret rejected.
- OAuth: random state cookie compared with `secrets.compare_digest`, cleared on callback;
  identity keyed on immutable `github_id`; dev login gated by env + flag + IP limiter.
- Sessions: hashed cookie with expiry; CSRF on unsafe methods; per-user rate limit.
- Tenancy: `require_project` returns 404 for non-members; artifacts, intelligence context,
  execution history and investigations check project membership; idempotency keys are
  per-user and replay only after authorization.
- Provider calls: repo connect, commit fetch, and assessment start verify live installation
  and user access before calling GitHub; delivery checks Verify verdict and owner authority
  before the write token.
- Installation revocation: `installation.deleted` / repositories removed detach
  `installation_id` and cached access; delivery and PR review fail closed on missing installs.
- Sandbox driver: `--network none` (or target-only internal network with a scope decision),
  non-root `--user`, `--cap-drop`, `--read-only`, `--pids-limit`, timeout + process-group kill.

## Unverified
- Sandbox flags were not executed against a live Docker daemon (none on this VM).
- Prompt injection was reviewed only at the architecture level (repo content is data; no
  tool grants follow from it); no adversarial-repo run.
- Concurrency of duplicate webhook deliveries under real parallel requests.

## Regression coverage
`backend/tests/test_security_audit_disconnect_writes.py` (9 tests: queued auto push,
queued PR-mode delivery audit, disconnect mid-delivery, queued PR review comment;
installation detached mid-delivery, disconnect / detachment immediately before the review
POST, disconnect / detachment during build-recipe drafting).
