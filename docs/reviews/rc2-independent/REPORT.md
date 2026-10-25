# RC2 — final independent security and merge-readiness review

## A. Exact-SHA decision

**Reviewed RC2:** `3f16c99fb728323ae464890862f84e16981e5f71`.
**Declared composition base:** `f8ab19e7587614b9741e2cd3433807c348b799d2`.
**Upstream comparison snapshots:** `4d4be9e395bfe6ab59b62962b688570e2d2d5261`, then `95e90861613afa362b1433020310174b074291c2` when #599 landed; final main observed at `eea084bc87ac6ca94f578073251c478655b09366` after #591 and #603.

- **Code-merging verdict: NO-GO for RC2 and the proposed transfer sequence as currently published.** Two P1 security failures and unresolved P2 recovery/authorization defects remain. Transfer migration/contract definitions also require correction and a tested combined tree.
- **Customer-deployment verdict: NO-GO.** Local scripted-provider success cannot override these failures or prove hosted/provider behavior.
- **Limited staging: isolated developer-owned rehearsal only**, with synthetic data, no customer secrets, provider responses scripted, enforcement disabled, and disposable databases. This is permission scope for validation, not security signoff or authorization to deploy.

All execution used the exact RC2 product tree. The mutable fork PR #8 had already moved to `8ddd6fb7…`; it was **not** substituted. Only an audit branch containing tests/evidence/report was written. No feature implementation, production edit, upstream-main change, PR approval, merge or deployment occurred.

The original reports were considered at immutable refs `6e882045` and `005ea42d`. Original assertions are retained. Passing old reproductions are distinguished below from stronger interleavings that still fail.

## B. Finding-resolution matrix

Severity is the prior finding's severity; closure applies only to this exact candidate and tested scope. PASS does not imply live-provider or deployed-system proof.

| Finding | Severity | Executed evidence / mechanism | Result and closure |
|---|---|---|---|
| F1 uncertain provider replay | P1 | Original strict crash regression passes; durable attempt reservation precedes send; unresolved attempts refuse replay. Actual child-process exit reaches recovery under explicit reconcile. | **PASS for no automatic second send; partial end-to-end recovery closure.** Claim/reconcile race and operator retry fail, N3. |
| F2 emergency capacity | P1 | Original assertion and bounded reserve, saturation/fairness/concurrent-claim tests pass in focused suite. | **PASS, closed** in RC2. |
| F3 lease fencing | P2 | Expired-owner completion/failure and heartbeat/new-owner races pass; audited original-owner late settlement remains explicit. | **PASS, closed** for original condition. |
| F4 deferral lifecycle | P2 | Real deferral records history and guards cancellation/deadline/effects; original regression passes. | **PASS, closed.** |
| F5 OFF cancellation | P2 | Queued/waiting cancelled, running flagged, recovery evidence retained and cancelled retry denied. Dependency completion cannot revive cancelled work. | **PASS, closed** for OFF. Disconnect is separately N1/R2. |
| F6 observability | P2 | Timed-out and recovery-required states do not appear as normal progress; both original cases pass. | **PASS, closed.** Secret-safe history remains N4. |
| F7 absolute queue deadline | P2 | Both enqueue sites persist original `deadline_at`; queue retries/waiting/provider slices do not reset it. Original and compat assertions pass. | **PASS, closed.** |
| F8 final-submit OFF race | P2 | Original OFF/submit regression passes; cancellation cannot be upgraded by ordinary final response. | **PASS for OFF, closed.** Repository disconnect after final read still fails N1. |
| F9 schema compatibility | P2 | RC2 schema is string `0.26.0`; generated contracts/TypeScript check pass, old exact 0.22 pin replaced by additive compatibility floor. | **PASS in RC2, closed.** Transfer branches have separate malformed versions N6. |
| F10 database-clock deadline test | P2 | Uses PostgreSQL transaction clock minus interval, not later Python wall clock. Original independent control passes. | **PASS, closed.** |
| R2 disconnect active work | P1 | Old first-response disconnect test passes, stopping further turns. Additional positive test retains settled attempt, synthetic incurred cost and transcript. New final-commit interleaving leaves invocation executed after committed disconnect. | **FAIL, open**; N1. |
| R3 reconnect stale cache | P2 | Old failed-personal-refresh test passes. New target-org case: successful unrelated personal refresh skips verification of revoked target installation and reconnect returns 200. | **FAIL, open**; N2. |
| R4 tenant picker ID | P2 | Original Bob/Alice shared-GitHub-visibility reproduction now returns no foreign connection ID; private resource remains 404. Broader job/artifact/investigation/isolation and non-superuser RLS tests pass. | **PASS, closed** for identified disclosure. |
| R5 abrupt death recovery | P2 | Original actual child `os._exit(71)` reproduction now enters recovery under explicit reconciliation. Fast reclaim can defer it back to queued before reconciliation; accepted operator retry leaves attempt unresolved. | **PARTIAL, open**; N3. No duplicate physical provider call established. |
| C1 credential redaction | P1 | Original job output and stored `last_error` are sanitized. New terminal failure still writes raw message to `job_events.reason`, returned through viewer-readable history. | **FAIL, open**; N4. |
| C2 project jobs API | P2 | Restored project-scoped jobs listing, coarse member errors and owner-sanitized detail covered by candidate tests. | **PASS, closed** for original missing endpoint/compatibility. |
| C3 commit failures | P2 | Merged compare fallback/permanent failure classification and terminal skipped evidence preserved; candidate auto-commit tests pass. | **PASS, closed** for original regressions. Later upstream quota change is separate. |
| C4 source secret redaction | P2 | Candidate source/output redaction tests include merged inline, DSN, key-value and parse-safe forms; security suite passes. | **PASS, closed** for original asserted forms. No claim of universal secret detection. |
| C5 telemetry quarantine | P2 | Candidate includes credential-value quarantine and its strict pilot-safety tests. | **PASS, closed** for original form. |

The original independent F1–F10 regression file differs from the original audit only in its explanatory docstring. No assertion was weakened, deleted or xfailed in this review. The five prior independent runtime probes were copied unchanged; migration tests only changed the pinned upstream snapshot/name. New failures remain strict.

## C. New or residual defects

### N1 — P1 — disconnect can commit after the final revocation read, then final output commits as executed

**Sources:** `backend/backend/services.py:302–343`; `backend/backend/live_defense/first_responder.py:1140–1205`; disconnect `backend/backend/api/routes.py:489–542`.

The disconnect writer locks the repository row. The corresponding final reader calls `repository_revocation()` with ordinary SELECTs, not the shared row lock. The final transaction's project advisory lock does not serialize with repository disconnect. After job-cancel/OFF/revocation reads have succeeded, the invocation is written as executed without re-checking under the repository lock.

**Reproduction:** `test_disconnect_after_final_revocation_read_prevents_success` wraps the actual production helper, calls it unchanged, and schedules the real owner disconnect API immediately after it returns None during final persistence. Disconnect returns 200 and commits. The unchanged real result is returned to the handler; draining leaves an executed invocation, so the negative assertion fails. Neither the authorization predicate nor invocation result is mocked. This is a deterministic schedule of the check→write race, not proof from a passing mocked assertion.

**Impact:** successful investigative output can be published after the customer revocation committed. Original callback checks resolve the normal case but not atomic final persistence. **Owner:** first-responder + hardening integration. Use consistent repository/mapping and invocation/job locking order across dispatch/final persistence/disconnect; revalidate under that boundary. Retain incurred cost and partial evidence. Avoid deadlock by reviewing lock order rather than adding isolated locks casually.

### N2 — P2 — unrelated personal refresh bypasses fresh organization-installation verification

**Sources:** `backend/backend/api/routes.py:611–620`; `backend/backend/api/github_repos.py:106` and `verify_installation_access`.

Reconnect treats a boolean “some personal installation refreshed” as proof for the target stored installation. For a user with personal install 123 and cached organization repo under install 456, successful refresh of 123 sets `refreshed=True`; the target 456 check is skipped and its cached access row survives.

**Reproduction:** `test_org_reconnect_checks_target_installation_even_with_personal_refresh` disconnects an owner fixture backed by org install 456, then supplies valid personal install 123 from the scripted GitHub boundary. The target org installation would return 404 if called. Actual result: **HTTP 200**, `installations verified=[123]`; expected 403. Production routing/cache checks run unchanged.

**Impact:** Ari reactivates a connection without fresh proof of the target grant. This does not prove GitHub would issue a token for a deleted installation. **Owner:** onboarding/hardening. Always verify the exact target installation/full-name pair or return a structured refresh result identifying which grant was verified. Test org installs, unrelated personal installs, 401/403/404, omitted target repo, 5xx/timeouts and membership changes.

### N3 — P2 — provider ledger and recovery state do not complete one coherent recovery protocol

**Sources:** `backend/backend/jobs.py:417–436` claim SQL; `backend/backend/worker.py:223–232`; `backend/backend/execution.py:43–79,177–200,529–589`; `backend/backend/live_defense/first_responder.py:944–952`.

Two independent actual abrupt-exit schedules fail:

1. **Fast claim before reconcile:** after child exit and lease expiry, `worker.run_one()` reclaims the job because claim tests only job `effect_state IS NULL`. The handler finds the in-flight ledger and defers to queued. The subsequent reconciler scans expired running jobs, so it no longer surfaces this queued unresolved request as recovery_required. Test confirms **zero new provider calls**, then fails because state is queued.
2. **Operator-confirmed retry:** explicit reconcile correctly parks the crash as recovery_required. The real owner recovery API accepts `resolution=retry` and returns 200, but only clears job effect fields; it does not resolve the associated provider attempt. Redelivery finds the old in-flight reservation and defers; scripted provider calls remain empty.

**Reproductions:** `test_fast_reclaim_cannot_hide_unresolved_provider_from_reconciler`, `test_operator_confirmed_retry_resolves_provider_ledger`. Original direct-reconcile abrupt-exit test passes, which is why its result alone cannot close R5.

**Impact:** unknown billable outcomes are not replayed automatically, but can disappear from operator recovery or an accepted manual recovery can fail to resume work. **Owner:** reliability + provider ledger. Fence claim against unresolved durable ledger state and reconcile queued/deferred uncertain work; make explicit operator resolution update the matching attempt/job atomically with provenance. Never infer “not applied” from lease expiry alone.

### N4 — P1 — sanitized job errors leak through persisted event history to viewers

**Sources:** `backend/backend/jobs.py:207–236,788–799`; `backend/backend/execution.py:498–513`; `backend/backend/api/execution.py:65–76`.

Terminal `jobs.fail` sanitizes `last_error`, but passes raw `error.message` to transition.reason. `record_event` stores reason/details unchanged; history API returns them to any project viewer. Thus the ordinary job API can be safe while another public project surface discloses the same infrastructure credential.

**Reproduction:** `test_viewer_history_does_not_bypass_job_error_redaction` fails a real queued/claimed job with a synthetic PostgreSQL DSN password. It first asserts the owner `/jobs/{id}` response does **not** contain the password (passes), then uses a viewer session to read `/jobs/{id}/history`. That endpoint returns 200 and contains the password in event reason. No real credential was accessed.

**Impact:** credentials embedded in backend exception messages are persisted and disclosed across the job-detail/history boundary. **Owner:** reliability + observability. Sanitize before storage at the event boundary, including reason/details/recovery notes where applicable; scrub historical rows/read paths and verify owner/member/viewer/outsider behavior.

### N5 — P2 / merge blocker — transfer branches still collide on migration revision 0018

**Pinned sources:** `ae414985…:backend/backend/migrations/versions/0018_execution_reliability.py:13` and `a68817fb…:backend/backend/migrations/versions/0018_repository_disconnect.py:6`.

Both declare `revision="0018"`, `down_revision="0017"`. RC2's actual chain is correct, but the published transfer set is not that chain. The mapping documents renumbering whichever lands second; that is an outstanding code change, not a merge-ready state. Strict Git-object assertion fails. Renumber/reparent the second migration before approval and replay the populated upgrade/rollback proof on the final assembled tree.

### N6 — P2 / merge blocker — two transfer branches have an empty-tuple schema version

**Pinned sources:** `9fc0429a…:shared/shared/__init__.py:8–52` and `a217d3c9…:shared/shared/__init__.py:8–52`.

AST evaluation gives `SCHEMA_VERSION == ()` in both observability and onboarding transfers: the parentheses contain comments but no version string. RC2 itself correctly has string `0.26.0`. The pinned transfer-manifest assertion returns `['0.23.0', (), '0.26.0', ()]` for the documented sequence.

**Impact:** canonical shared version/type and generated consumers cannot match tested RC2. **Owner:** transfer integration + shared-contract owner. Correct the declarations, resolve shared union/version order once, regenerate contracts, and test the actual transfer composition. Do not infer validity from the mapping's claimed 0.24/0.25 labels.

## D. Test execution and limitations

### Reproduced evidence

- Focused F1–F10/compatibility/reliability/tenant/RLS/hardening/readiness/migrations: **122 passed**.
- Original independent prior runtime probes + latest-main forward and populated migration roundtrip: **7 passed**.
- Ordinary response-time disconnect preserves settled attempt, synthetic cost, and transcript: **1 passed**.
- New runtime interleavings: **five strict failures** (N1, N2, two N3 schedules, N4).
- Transfer-manifest checks: **2 failed**, N5/N6. The original first schema probe raised a tuple conversion error; it was corrected to assert the version's required string type explicitly. Both raw and final outputs are retained; no failing production condition was hidden.
- Code intelligence/privacy suite: **74 passed, 1 skipped**.
- Combined security agents, shared contracts and cross-security: **740 passed, 24 skipped**. These overlapping suites are not summed with other totals.
- Generated contract/TypeScript suite: **95 passed**; generated exports current; configured mypy passes **41 source files**, not the entire backend under strict typing.
- Frontend: **365 unit tests passed**, **35 transport tests passed**, ESLint/TypeScript/production build passed.
- Local readiness: **25 PASS**, including its own nested 18-check release checklist and 15-check HTTP smoke. Those nested counts are not extra independent suites. Scratch PostgreSQL/local services/dummy secrets only.
- Full original backend, initial run: **652 passed, 1 failed, 8 skipped, 1 setup error**. The failure is an unchanged fixed-one-second startup SIGTERM test. The setup error came from setting `REHEARSAL_LIVE=0`: this test gates on variable presence, so zero still enables it and it failed before execution at missing `/Users/devin/repos/pilot-rehearsal-target`. No live provider request was made. Corrected rerun unsets that flag.
- Full backend corrected rerun: **651 passed, 2 failed, 9 skipped; both failures are the unchanged fixed-startup-delay SIGTERM tests**.
- Unchanged isolated SIGTERM file: **2 failed** with processes exiting -15 before the presumed ready point. Readiness-synchronized independent control: **1 passed**, requiring observed job entry before the same SIGTERM/finished-once/exit-zero assertions. Treat original timing-based test reliability as unresolved; do not advertise an entirely reproduced green backend run if it still fails.
- Real-stack Playwright: **49 passed in 23.8 minutes, no retries**. No retries are added by this audit.

Live Anthropic/Vercel and real sandbox isolation were not proven. Optional live-provider/container tests remain skipped and explicitly listed in output. Existing RL integration tests initially skip without optional dependencies; no new research training/evaluation, checkpoint promotion or enforcement was performed. Browser model interactions are scripted; incidental backend retry diagnostics are not interpreted as live-provider success.

Commands, environment, exit outcomes, original-vs-new test provenance and sanitized logs are in `evidence/README.md`. New audit files were excluded only from the **original** full-suite rerun so its original count remains interpretable; every new negative probe is run separately and retained strictly, not skipped/xfail-hidden.

## E. Upstream compatibility and transfer audit

### Adam's composed and post-base work

RC2 includes the declared `f8ab19e7` source, and preserves the previously missing merged jobs API/redaction, GitHub commit failure/fallback handling, source privacy, quarantine, tenant RLS, shared quotas/rate limiting, manual-first defaults, sealed verified delivery and ops/readiness surfaces. Relevant candidate tests run through real local services.

Current main subsequently added:

- **#596**, true quota reset time when count exceeds the limit. Two exact current-main regression tests fail against RC2's older quota implementation. They are tracked as **post-base behavior absent from the frozen candidate**, not reintroduced original F1–C5 security regressions. Preserve the merged implementation in any upstream assembly and rerun its tests.
- **#597**, data-volume alert/report fields. RC2 predates these additive ops/settings/maintenance changes. Preserve them in the ops transfer merge; this audit did not run a hosted volume alert.
- **#599**, recipe-declared protected-tests propagation to independent Verify. RC2 predates it; existing configured/expectation-derived protected-test paths remain present. The exact current-main repo-declared-path regression **fails** against RC2: the orchestrator returns an empty protected-test list for the recipe fixture. The result is recorded separately as missing post-base #599 behavior. Do not replace current orchestrator/workspace code with the older RC2 copy. The sealed verified-diff delivery path already merged in RC2's base is a separate guarantee and was not conflated with this new propagation feature.

- **#591**, blank assessment SHA resolves through trusted GitHub default HEAD, with matching schema/frontend changes; #603 is a health handoff. These landed during final publication. The source diff was inspected, but this new absent-in-RC2 path was not executed against RC2. The final merge must retain the trusted SHA resolution and place disconnect/authorization checks before its new repository network read. Migration files are unchanged through final main.

These upstream additions were inspected separately from RC2. No whole-tree rollback to RC2 is approved. UI/navigation/onboarding changes were exercised against RC2 itself; a future combined tree needs its own browser verification after retaining newer upstream changes.

### Migration proof for RC2 itself

RC2 has the expected single head:
`0015 → 0016 tenant_rls_intelligence → 0017 worker_heartbeats → 0018 execution_reliability → 0019 repository_disconnect`.

Fresh install passes in backend/readiness runs. Exact upstream migration tree → RC2 upgrade passes. Populated `0017 → 0019 → 0017 → 0019` preserves existing jobs/heartbeat rows and project backfill, distinct `worker_heartbeats`/`worker_registry`, and enabled/forced tenant RLS. Non-superuser probe-role isolation passes. No `alembic stamp` was used. Old conflicting fork-stamped staging databases remain a separate lineage requiring inventory and an explicit tested conversion if any exist.

### Sequential squash equivalence

Transfer mapping reviewed: `coordination/messages/2026-10-25-upstream-transfer-mapping.md`. Most transfer branches are based exactly on `f8ab19e7`; direct ops #5 instead has older merge base `35e8b32c`. Workstream path lists are captured. They are not a substitute for a proven combined tree.

A **read-only merge-tree / unreferenced virtual squash simulation** starts at current upstream `4d4be9e3`, then #412, #458, reliability, in the proposed order. No branch/HEAD/worktree production file or remote ref is merged. #412/#458 encounter documentation conflicts. Continuing only through documentation-conflicted virtual trees, reliability then hits **production conflicts in `backend/backend/live_defense/controls.py` and `backend/backend/worker.py`**. The audit stops rather than inventing security-sensitive resolutions.

Consequently, **no complete final merged tree exists from the published inputs without further choices**, and it cannot be certified equal to RC2. On top of conflicts, N5/N6 require actual changes. No transfer diff contains RC2's exact `first_responder.py` glue; current #458 has a different revocation implementation. They may be reconcilable, but its independently green CI does not prove equivalence to the tested RC2 path. Ops #5 also needs its older script/router additions unioned with later maintenance/auth/default-author changes, not a file replacement.

### PR-by-PR authorization matrix

GO/HOLD/NO-GO applies to the exact listed source/transfer; no GitHub approval was submitted. Historical fork heads are not approved merely because corrected copies exist in RC2. Every production merge requires contract/migration/security checks on its resulting SHA, and the last combined SHA requires full integration/browser gates.

| Logical PR | Exact source / upstream-targeted transfer | Decision | Required order / additional checks |
|---|---|---|---|
| upstream #412 | `4ecd7558c20d676985294073d5a818a538bdf78c` | **HOLD** | First prerequisite; documentation conflicts and composed contract/export gate need a reviewed landing SHA. No new feature-logic defect attributed to this PR alone. |
| upstream #458 | `8396e836866e33ebc34a402a7c8bd0eb6bc769d8` | **HOLD** | After #412. Different implementation from frozen RC2; reconcile revocation/provider-ledger glue with reliability and hardening, then rerun N1–N4. Individual green checks do not approve the composition. |
| fork #1 reliability | source `6063d9b57ff8aa0685bf4a94f54e7bcd49656758`; transfer `ae414985d09796cc950b7e833157861d239abc29` | **NO-GO** | After prerequisites; N3/N4, worker/control production conflicts, and N5 migration composition. Test claim-before-reconcile, owner resolution, history sanitization and heartbeat/lease union. |
| fork #2 E2E | historical `247c23124ab167e8edf8cafac2d959f1d94b5ca0`; no separate transfer | **GO for retaining test-only assertions; HOLD release landing** | Folded into final integration per mapping. No standalone production approval. Retain new adversarial probes and execute against the resulting final tree. |
| fork #3 observability | source `92e0009610659a1bab42f722e2990459ca48fd96`; transfer `9fc0429a71781a53815982b1c9426c9330989506` | **NO-GO** | After reliability/7C contract agreement; N6 empty tuple and N4 viewer history boundary. Regenerate shared union and verify read APIs/consumer types. |
| fork #4 hardening | source `356cd5352270e25e0907aa61de6bf094449c4c71`; transfer `a68817fbda7e37e8cd0fd597458d8c606015e0d9` | **NO-GO** | After reliability; renumber/reparent disconnect migration to 0019 before landing, fix N1 shared locking and exercise revoked running/waiting/recovery work. |
| fork #5 deployment/ops | `c7c5336f79a9172b27e03d9570e7ae708b1f78b1` direct branch | **HOLD** | Old base; preserve upstream storage/maintenance, Bearer ops protection and empty default auto-author policy. Run #597 tests, preflight, backup/restore, real drain/restart and deployment pairing after assembly. |
| fork #6 onboarding | source `41b77fc20ceaec8970bb00216423bb965cea8155`; transfer `a217d3c984138cdaf6ef4ee238234e4fba7fbe17` | **NO-GO** | After corrected hardening/contracts; N2 target-org verification and N6 schema type. Current role/tenant/onboarding/browser checks must accompany the exact landing. |
| fork #7 validation | source `16fa812228e04e52e59d773a207075f781f51a17`; transfer `7ba1ab7707d52716dcae118de0f78b805ac15fde` | **HOLD for final release gate** | Last, after reconciled runtime/ops. Local rehearsal is useful, but current checks miss N1–N4 and cannot authorize release. Extend the gate and rerun on assembled SHA. |
| fork #8 / RC2 | **`3f16c99fb728323ae464890862f84e16981e5f71`** | **NO-GO** | Runtime security failures remain; published transfer plan is not tree-equivalent. Mutable #8 metadata is recorded only for coordination. |

No sequential order can repair the current defects by itself. Correct the branch inputs and publish the expected final tree/diff manifest before asking for a final merge approval.

## F. Final release gates

1. Resolve N1–N4 in production and retain their new strict tests; prove shared-state boundaries across disconnect, send/reservation, final persistence, lease recovery and explicit operator settlement.
2. Correct N5/N6 on the transfer branches, not only in an integrated working copy. Freeze exact prerequisite/transfer SHAs and reviewed conflict resolutions; regenerate all shared contracts and publish the final tree hash plus intentional differences from the retested RC.
3. Preserve latest upstream authentication, GitHub lifecycle, quota reset, storage alerts, sealed delivery and recipe-protected tests. Rerun corresponding current-main tests against the actual assembly. Do not reset main or overwrite another owner's files.
4. Reproduce original full-suite CI including stable worker drain; keep initial failures/environment limitations visible. Run final frontend/browser, migration/RLS and local readiness on the same SHA.
5. Inventory actual staging DB lineage, perform backup/restore/rollback and non-superuser RLS proof, then authorized external GitHub/OAuth/installation-revocation and real sandbox/worker/deploy-pairing evidence. Any paid live-provider test requires separate explicit scope; none is implied by this report.
6. Customer enforcement remains disabled; no research training/checkpoint promotion is part of approval. Obtain independent exact-SHA signoff after fixes. **Any remaining P0/P1 or unproved critical invariant keeps NO-GO in force.**
