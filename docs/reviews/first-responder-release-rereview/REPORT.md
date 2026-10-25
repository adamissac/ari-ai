# Independent release re-review — NO-GO

Reviewed release: **dd530ae3b00d31ecc54a6fb5908a50b8b6b1965d**, fork PR #8.
Upstream comparison: **dc9a623aca21678bd34a84d61a4bb8433445a59f**.
Standalone E2E PR #2: **611c38ce55e3acd487812b551a9ecdc05908318c**.
Original audit: **6e88204574a93333b8329b46eeeb5e7bab373843**.

This is a new source and executable review of the updated release, not a restatement of the original findings. Product code was not changed. Independent regression files added on the audit branch intentionally fail. No merge, deployment, customer enforcement, live provider request, or new research experiment was performed.

## Decision

**NO-GO for upstream merge or customer deployment at the reviewed release SHA.** Two P1 and three P2 findings remain below, reproduced by six failing test cases. No new P0 was established. The isolated fresh-database local readiness rehearsal passes; that result does not establish migration compatibility or customer revocation safety.

The original strict regressions now pass. Most original defects have real source fixes. F1 remains only partially resolved: the durable invocation ledger prevents replay, but the recovery bridge does not survive abrupt process termination. Do not describe all ten findings as unconditionally closed.

## Original F1–F10 resolution matrix

| ID | Independent result | Source verification and limits |
|---|---|---|
| F1 — uncertain provider replay | Original regression passes; **partial closure**, R5 | `provider_ledger.reserve_attempt` commits a row-locked reservation before sending. The wrapper blocks unresolved attempts; replay is refused. Exception handling marks uncertainty and bridges to job recovery. Actual process exit skips that bridge, leaving a queued job and in-flight ledger. No duplicate physical request was demonstrated. |
| F2 — emergency capacity | Resolved in pinned release | `jobs.claim` uses a narrowly enumerated emergency/rollback/expiry reserve, default 2, separate from ordinary caps. Advisory transaction lock serializes claims when limits apply; `SKIP LOCKED` prevents duplicate claims. Saturation, bounded emergency capacity and concurrent project-cap tests pass. |
| F3 — expired lease completion | Resolved | Ordinary `complete` and `fail` require a valid lease/owner. Explicit original-owner late settlement of `recovery_required` remains a separately audited exception. Expired-owner and heartbeat race regressions pass. |
| F4 — deferral history | Resolved | The shadowing legacy `defer` was removed. Remaining implementation records lifecycle events, cancellation/deadline precedence, dependency state, retry-neutral defer counts, and rejects uncertain effects. |
| F5 — OFF misses waiting work | Resolved | OFF covers queued, waiting, running and recovery-required first-responder jobs. Recovery evidence is retained and cancellation blocks operator retry. Independently authorized cleanup/control work is preserved. |
| F6 — misleading progress | Resolved | Invocation views and final-state precedence account for timed-out/recovery-required jobs. Both original parameterized cases pass. |
| F7 — durable queue deadline | Resolved **in integration only** | Both agent-step enqueue sites pass `deadline_at=decision.deadline_at`; invocation/payload/provider share the remaining absolute deadline. Original and compatibility assertions pass. Standalone #2 still lacks this integration change. |
| F8 — final-submit OFF race | Resolved for OFF | Runtime cancellation checks and final persistence refuse to upgrade cancelled invocations; late transcript/usage evidence can be retained. Does not imply repository disconnect is covered: R2 reproduces that separate missing gate. |
| F9 — exact schema pin | Resolved | Exact 0.22 equality changed to a version floor; current schema 0.25 and additive models remain exported. Generated-schema freshness, roundtrip tests and TypeScript compilation pass. Floor alone would be weak; actual contract checks were also run. |
| F10 — PostgreSQL deadline clock | Resolved | Compatibility regression sets deadline using database `now() - interval`, so the test no longer mistakes Python wall-clock time for transaction time. Independent DB-clock control passes. |

### Regression integrity

`test_independent_integration.py` differs from the original audit **only in its docstring**; assertions and fixtures are unchanged. No strict xfail remains in that file. Scenario E was intentionally changed from replay-to-success to failed/no-replay and now counts physical provider requests, which is a stronger check than counting logical invocation rows. F9's exact-version assertion was relaxed to a floor for additive compatibility; generated contract and consumer checks supply the substantive proof. F10's clock change fixes the test rather than hiding a timeout failure.

The remaining blind spot is crash simulation: a caught Python `BaseException` is not abrupt worker death. The original test allows the new exception handler to finish its database writes. R5 uses a child process exiting inside the scripted provider after reservation, so no Python cleanup handler runs.

## New findings and actual reproductions

### R1 — P1: reused migration identities silently accept incompatible databases

Sources: release `0016_execution_reliability.py`, `0017_repository_disconnect.py`; upstream `0016_tenant_rls_intelligence.py`, `0017_worker_heartbeats.py`; `backend.preflight.migration_status`.

Both chains use revisions `0016` and `0017` for different changes. The problem is **already present in latest main**, not merely hypothetical competing open PRs. The single-head unit test returns `["0017"]` for either chain and cannot distinguish their meaning.

Reproduction: `test_latest_upstream_database_can_upgrade_to_release[main_to_release]` creates a disposable database, applies the exact pinned upstream scripts, then the release scripts. Both upgrade calls succeed, but jobs still lack `deadline_at`, `effect_state` and `defer_count`. Release workers consequently cannot use the expected schema. Conversely `[release_to_main]` applies release then upstream; upstream migration reports completion while `index_payloads` has neither enabled nor forced RLS. These are two real PostgreSQL executions, not string comparisons.

The heartbeat schemas also conflict: release uses `last_seen_at/state/jobs_finished`, while main uses `heartbeat_at/last_poll_at`; renumbering filenames alone cannot reconcile the table. Existing stamped databases need explicit forward conversion and validation. Do not stamp around the mismatch or rewrite already-applied upstream history. Preserve upstream tenant RLS, reconcile heartbeat consumers and append uniquely identified reliability/disconnect upgrades. Test populated latest-main and any already-installed fork databases, plus fresh install and supported rollback.

### R2 — P1: disconnect permits additional provider turns in an active investigation

Sources: `backend/api/routes.py:499` disconnect cancellation sweep and `backend/live_defense/first_responder.py:1089` cancellation callback.

Disconnect revokes deploy mappings and cancels assessments/queued repo jobs, but the active agent-step carries project/decision/invocation IDs and is not selected by the repo-ID queued-only sweep. Its per-turn callback checks OFF and job cancellation, not repository disconnection or mapping revocation. A mapping checked before the loop is not revalidated during the loop.

Reproduction: `test_repository_disconnect_stops_next_provider_turn` uses the normal owned fixture and real API/queue/runtime, disconnects through the owner API after the first scripted provider response, then drains. Disconnect returns 200, but **four provider turns total** occur: **three new turns after disconnect**. This establishes post-revocation investigation activity; no live data transmission or customer provider billing was attempted in this review.

Required correction: link active steps to their trusted repository/mapping, signal cancellation across queued/waiting/running steps, and re-check revocation before each new provider/tool operation and final execution persistence. Preserve already-incurred costs/evidence, avoid restoring revoked mappings on reconnect, and serialize against disconnect so a check cannot authorize a later send indefinitely.

### R3 — P2: reconnect fails open on stale cached repository access

Sources: `backend/api/routes.py:559–580`; `backend/api/github_repos.py:82–99`.

The refresh helper swallows configuration/HTTP failures and leaves old `github_repo_access` rows intact. Reconnect then treats the old row as current authorization. Organization installations do not receive this personal-installation refresh at all.

Reproduction: `test_reconnect_refuses_stale_access_when_fresh_check_fails` seeds previously trusted access, disconnects, and makes the GitHub installation check return an HTTP 404. The real reconnect API responds **200**, clears `disconnected_at`, and preserves the stale installation. The test actually invokes the failing fake GitHub client (captured `HTTPStatusError` warning), rather than accidentally stopping at missing local credentials.

This proves reactivation without fresh proof; it does not prove GitHub itself will serve a revoked installation token. Fail closed (403 for revoked access, 503 for unverifiable context), including organization installations and permission changes. Upstream #540 proposes `verify_installation_access` for connect, but its branch does not include this release's reconnect route: reconcile both boundaries explicitly.

### R4 — P2: repository picker leaks another tenant's connected repository ID

Source: `backend/api/github_repos.py:157–174`.

`/github/repositories` filters the access-cache side by current user but joins repositories globally by `full_name`, without project membership. A user legitimately able to see the same GitHub repository can learn another Ari tenant's connection ID/state. Reproduction `test_repo_picker_does_not_disclose_other_tenant_connection`: Bob receives 404 for Alice's repository resource but the picker returns Alice's repository ID as `connected_repo_id`.

Impact established: cross-tenant connection metadata disclosure. No source bytes, artifact contents or write access were obtained. Filter the joined connection by authorized project/organization membership, and test that public/shared GitHub visibility does not confer Ari tenant membership.

### R5 — P2: provider recovery bridge is written only by exception cleanup

Sources: `provider_ledger.py:92–120,181–206`, `agent_execution.py:276–303`, `first_responder.py:944–952`, `execution.py:112`.

The ledger idempotency key is local request metadata; this review does not establish provider-side deduplication. Reservation is durable, but job `effect_state` is marked only in `mark_attempt_uncertain`, after a Python exception is caught. Abrupt death after send skips both cleanup and the separate bridge transaction. Reconciliation sees no job effect and requeues it. On redelivery, the ledger refuses an in-flight attempt through `JobDeferred`; no operator recovery state is established by this path.

Reproduction: `test_abrupt_process_death_during_provider_send_requires_recovery` forks a worker process, calls `os._exit(71)` inside the scripted provider, confirms that exit code, expires the persisted job lease and runs the real reconciler. Observed job status: **queued**, expected **recovery_required**. This is an incomplete recovery/observability guarantee, **not evidence of a replayed billable call**. Commit the job's request effect atomically with the pre-send reservation, or make reconciliation consult the durable invocation ledger. Settlement must clear the matching effect safely, with owner/attempt fencing and audited operator resolution across both state machines.

## Migration compatibility report

- Fresh release installation: passes through release `0017`.
- Populated original `0015 → 0016 → 0015 → 0016`: passes, existing rows and project backfill retained.
- Synthetic parallel-head upgrade/downgrade and release single-head check: pass, but do not cover actual main collision.
- Pinned latest-main `0017 → release`: **FAIL**, migration no-op with required columns missing.
- Release `0017 → pinned latest main`: **FAIL**, tenant RLS silently omitted.
- Physical heartbeat table and API/worker readiness contracts need consolidation, not duplicate creation.
- Existing latest-main RLS uses forced tenant policies; preserve transaction-scoped tenant context and prove behavior under a non-superuser runtime role. Superuser test success is insufficient for RLS.

## Latest upstream and parallel work

Snapshot metadata and open-PR list are retained in `evidence/`. PR #8 was reported `CONFLICTING`, with no status checks in `statusCheckRollup` at the metadata check; local passes are not GitHub CI signoff.

- Upstream main `dc9a623a` includes tenant RLS (`b41edefd`, original #535 is closed), worker-heartbeat/capability-readiness/deploy pairing changes (#533, merged), connect navigation (#496), pilot package (#527), retention/volume ops (#558), code-review evaluation gate and rehearsal coordination (#564–566). The release does not incorporate this current main.
- #458 now points to `980352445f52f7043feeba97318a5d9f3478c389`, after merging main. Its provider implementation still lacks the release-only job-recovery bridge and both durable enqueue arguments. A blind replacement with its files regresses integration fixes. Diff captured.
- #412 remains open at `4ecd7558c20d676985294073d5a818a538bdf78c`: already represented in the integrated branch; avoid duplicate reimplementation.
- #530 release gate merged as `22454ef2` during final review: overlaps routes/jobs/redaction/CI; preserve current release lifecycle and cancellation behavior when integrating.
- #540 onboarding hardening remains open at `1debeed9b16e9ed6ac4be406327ba792104ed91f`: overlaps GitHub access, routes, installation lifecycle, auto-commits/pipeline. Preserve release disconnect/reconnect and add fresh authorization checks to both connect and reconnect.
- #531 intelligence/redaction audit merged as `ac87a290` during final review; #532 Defense Lab safety/quarantine remains open. Preserve new job-error redaction, parse-safe source redaction, retrieval benchmarks and negative tests without changing frozen RL research results or claiming new training evidence.
- #538/#536 frontend changes are open and overlap a rapidly changing console; reconcile against already merged #496 and regenerate transport consumers after contract decisions.
- #567 ops import-shadow fix merged as `5a56e44c` during the review; main then advanced to `f78637de` with #569 coordination status. Main then advanced to `dc9a623a` as #530/#531 and merge records for #496/#527 landed. The migration directory is byte-identical to f78637de, and the pinned compatibility reproductions were rerun. Preserve the corrected diagnostics/readiness import and new redaction protections when recomposing.

## Standalone E2E PR #2: F7 investigation

At **611c38ce55e3acd487812b551a9ecdc05908318c**, the compatibility suite gives **7 passed, 1 strict xfailed**. Running the marked test with `--runxfail` gives **1 failed** because an agent-step `jobs.deadline_at` remains null. This is a real missing queue enqueue argument in that composition, not an obsolete expected failure or incorrect mock. Integration PR #8 adds the absolute deadline in both enqueue paths and passes that same assertion. Propagate those changes to the eventual merge composition before removing the marker. Do not delete the negative assertion or claim standalone #2 is fully green.

## Executed checks and evidence limits

- Pinned release backend: **510 passed, 8 skipped**. Original regressions are included. Four skipped RL-dependent files were subsequently covered by the dependency-enabled integration run below.
- Original focused audit/compatibility/provider review + populated/parallel migrations: **47 passed**.
- Combined security agents + shared contracts: **712 passed, 24 skipped** (live-provider/Docker/TypeScript availability gates).
- Cross-subsystem security plus generated TypeScript contract check: **114 passed**; supplies the compiler check skipped above.
- Backend RL integration/expectations plus runtime ingest: **14 passed** with existing installed RL dependencies. Existing software smoke only; no new research run, tuning, promotion or enforcement.
- Frontend unit tests: **347 passed**; transport **35 passed**. ESLint, TypeScript, frontend production build passed.
- Generated examples check: **179 files, zero changes**; generated schema freshness passed. Configured mypy: **41 files**, passed; this is not strict typing of the entire backend. Ruff and formatting checks recorded in evidence.
- Local `deploy/release_readiness.py`: **25 PASS**, fresh scratch database, dummy secrets, local API/worker, backup/restore and alert sink. Its embedded release checklist adds 18 checks and HTTP smoke 15; these are nested checks, not extra independent suite totals. No actual external GitHub/OAuth/provider, hosted deployment, or production sandbox security was established.
- Real-stack Playwright: **49 passed (9.4 minutes), no retries**.
- New independent probes: **6 failures**, covering five findings (R1 has two migration directions). Retained as strict assertions, no xfails.

Raw outputs (sanitized for synthetic fixture secrets) and exact-SHA metadata are under `evidence/`. Backend suite capture preceded addition of the deliberately failing independent probes; they were then run separately. All product source remained at the pinned SHA throughout tests. Browser assessment logs can include retryable `SNAPSHOT_NOT_READY` diagnostics; evaluate the final suite exit/result, not isolated log lines.

## Security signoff and safe sequential merge order

**Withhold security signoff. Do not merge or deploy this reviewed SHA.** The order below is a conditional engineering sequence, not authorization to merge anything:

1. Start a reviewed recomposition from latest upstream main; retain its already-merged tenant RLS, worker readiness/deploy pairing, retention and console changes. Establish a forward migration plan for both deployed lineages before importing the release chain.
2. Integrate #412 prerequisites only where not already represented. Reconcile reliability and shared contracts, then Phase 7C/provider reservation and recovery together: uniquely identified forward migrations, one compatible heartbeat table, matching consumers, preserved tenant policies and atomic reservation→job recovery.
3. Integrate customer hardening and #540 installation lifecycle with R2/R3/R4 fixes; then onboarding. Keep `disconnected_at` authoritative, keep audit installation IDs, preserve revoked mappings and explicit opt-in after reconnect. Verify member removal, organization installation changes and active-loop cancellation.
4. Integrate observability consumers against that final lifecycle/contract; preserve cancelled and unknown outcomes, usage evidence and audited late settlement. Apply E2E #2 tests after its F7 assertion passes without xfail.
5. Reconcile #530 CI gate, deployment/ops/readiness, #567 diagnostics import fix and relevant #531/#532 audit regressions. Ensure checks actually run for the exact composition and Linux/PostgreSQL runtime role.
6. Reconcile onboarding/console frontend changes (#538/#536 where selected) after canonical contract regeneration; rerun browser/API paths, combined suites and migration matrices on the resulting exact SHA. Obtain independent re-review before any merge/deployment decision.

Prefer a single pinned integration candidate with reviewed prerequisite PRs rather than merging mutually inconsistent standalone heads in any order. Avoid dropping release-only F7/recovery changes when taking refreshed #458, and avoid overwriting latest-main RLS/readiness with older integrated files.

## Remaining staging/customer blockers

- Resolve R1–R5, retaining the new failing tests as acceptance gates.
- Demonstrate conversion of populated latest-main and any fork-installed databases, backups/restore and supported rollback, plus tenant-policy enforcement using a non-superuser role. Do not mutate a customer database for this test.
- Re-run CI and readiness on the final immutable SHA; PR #8 metadata supplied no green check evidence and reports conflicts.
- Real deployment pairing, worker liveness/stopped-poll detection, configured alert delivery, durable volume/retention and rollback rehearsal must match the chosen upstream contracts.
- Real GitHub OAuth/install/uninstall/repository-removal and permission revocation, including organization installations, need authorized staging evidence. Local fake-provider API/browser results are not external-provider signoff.
- Any live paid-provider or real sandbox proof remains explicitly opt-in and separately scoped. Customer enforcement and new RL training remain outside this review.
