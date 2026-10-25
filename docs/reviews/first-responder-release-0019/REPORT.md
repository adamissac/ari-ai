# Independent frozen-candidate re-review — NO-GO

**Release tested:** `070f75a9987658ef8b816cba412859f7b5c1c948` (fork PR #8).
**Latest upstream inspected:** `2c825c4e9e6e1dca305c504fde46cdda0b8cbf16`.
**Previous release reviewed:** `dd530ae3b00d31ecc54a6fb5908a50b8b6b1965d`.

## Verdict and approval scope

**NO-GO for production release and for merging the current integration PR as-is.** Migration reconciliation is substantially fixed, and all original F1–F10 regression assertions pass without xfails. That does not close the independently reproduced provider-recovery, revocation and tenant-metadata defects, or establish semantic compatibility with Adam's newer merged work.

This review ran real local PostgreSQL/API/queue/runtime tests with scripted providers. Product source stayed at the frozen SHA; only audit tests and reports were added. No paid provider calls, customer enforcement, merge or deployment occurred. GitHub reported PR #8 `CONFLICTING`, with `statusCheckRollup=[]`; local test success is not remote CI signoff.

## Executed verification

| Check | Result | Meaning |
|---|---|---|
| Frozen candidate backend suite | **558 passed, 9 skipped** | Candidate's own tests, collected before new audit files were added. Includes original F1–F10 and compatibility assertions. |
| Focused original regressions + queue reliability + tenant isolation/RLS + ops readiness + migrations | **97 passed** | Concurrent claim/reconcile, emergency reserve/caps, lease fencing, uncertain generic effects, OFF waiting/recovery cancellation, non-superuser tenant RLS, latest-main migration and populated roundtrip. |
| Security agents + shared + cross-subsystem security | **739 passed, 24 skipped** | Scripted providers; live-provider/container gates skipped. |
| Independent follow-up probes | **5 failed, 1 passed** | Four prior runtime findings still reproduce; new job-credential exposure fails; latest-main forward migration now passes. |
| Exact latest-main jobs/GitHub/auto-commit tests transplanted without assertion changes | **9 failed, 47 passed** | Actual semantic incompatibility with merged #530/#540, not a textual merge conflict alone. |
| Exact latest-main privacy tests, selected redaction cases | **1 failed, 2 passed, 4 deselected** | Mid-line secret values survive source redaction. |
| Newly merged #570/#532 redaction/privacy/pilot-safety tests | **20 failed, 38 passed** | Added while upstream advanced; source and failure traces retained. |
| Refreshed standalone E2E PR #2 at `247c2312` | **8 passed**, zero xfails | F7 marker has now genuinely been removed after deadline enqueue changes. Supersedes the previous standalone `611c38ce` result. |
| Local release readiness on frozen candidate | **25 PASS** | Scratch database, dummy credentials, local API/worker/alert sink, backup/restore. The script reports GO for its own limited checks. |
| Generated contract compiler/freshness and configured mypy | **95 contract tests passed**, export checked 180 files with zero changes, mypy passed 41 files | Kept separate from runtime security signoff. |

Counts overlap; do not sum them into a distinct-test total. The original full backend suite omitted optional RL dependencies and live/container checks as shown in its skip summary. Frontend build/browser tests were not rerun for this frozen candidate; earlier-SHA browser passes are not reused as exact-SHA evidence here.

## F1–F10 resolution matrix

| Finding | Strict regression | Independent source conclusion |
|---|---|---|
| F1 provider-attempt recovery/replay | PASS | **Partial closure.** Pre-send invocation ledger is durable and refuses replay; the bridge to job recovery is still written only by Python exception cleanup. Abrupt process exit remains R5 below. No second billable request was demonstrated. |
| F2 emergency capacity | PASS | Bounded emergency-stop/rollback/expiry reserve, default 2; ordinary/project/global caps cannot consume the reserve. Claims serialize under advisory lock. Saturation, bounded reserve and concurrent claims pass. |
| F3 lease fencing | PASS | Normal completion/failure requires valid owner/lease. Original-owner late settlement of uncertain effects remains explicitly audited. Race regressions pass. |
| F4 lifecycle deferral | PASS | Legacy shadowing definition removed; surviving defer records events, honours deadline/cancel/effect guards, and does not consume retries. |
| F5 OFF cancellation | PASS | Waiting jobs cancelled; running jobs flagged; recovery evidence retained and operator retry blocked after cancellation. Control cleanup remains separate. |
| F6 observability | PASS | Timed-out and recovery-required jobs are not presented as ordinary in-progress work. Both original cases pass. |
| F7 durable deadline | PASS | Both agent-step enqueue paths persist original absolute deadline. Queue wait/redelivery/provider budget use that deadline. Current standalone #2 also passes. |
| F8 final-submit OFF race | PASS | Cancellation cannot be upgraded to executed; late usage/transcript evidence retained. Repository disconnect is a separate missing cancellation gate, R2. |
| F9 schema compatibility | PASS | Additive version floor plus generated union/consumer checks; current schema 0.26.0. |
| F10 DB-clock deadline test | PASS | Uses PostgreSQL `now() - interval`, eliminating the previous wall-clock/transaction-clock mismatch. |

The original independent regression source differs from `6e882045` **only in its docstring**. Assertions were not weakened. The current original/compatibility files contain no xfails. Broader original-provider review tests remain in the backend suite. The follow-up probes are strict failing assertions, not xfailed away.

## Migration compatibility: R1 closed for latest-main lineage

The release preserves upstream migration files `0016_tenant_rls_intelligence` and `0017_worker_heartbeats` byte-for-byte, then adds `0018_execution_reliability → 0019_repository_disconnect`. Single head is **0019**.

The release's operational registry is now **worker_registry**; Adam's **worker_heartbeats** retains `heartbeat_at/last_poll_at` and the liveness consumer. The worker writes both appropriate surfaces and removes both on shutdown. This resolves the earlier same-table/different-schema collision.

Actual database proofs:

1. Apply exact latest-main migration scripts to disposable PostgreSQL, then candidate scripts: job deadline/effect/defer columns are present. The previous silent no-op reproduction now passes.
2. Populate upstream 0017 with an existing job and heartbeat row; upgrade **0017 → 0019**, downgrade **0019 → 0017**, and re-upgrade. Job and heartbeat data survive; project backfill is correct; tenant RLS remains enabled and forced; both registry tables have the expected distinct schemas.
3. Existing adversarial RLS tests use a non-superuser probe role: missing tenant context reads zero rows, foreign context reads zero, correct context reads its own row, and wrong-tenant writes fail. These pass.

This validates **latest-main/fresh database lineage**. Databases previously stamped 0016/0017 by the old conflicting fork migrations are a different lineage; automatic conversion of such installed databases was not demonstrated. Inventory any such staging databases and provide a tested explicit conversion before using them. Do not use `alembic stamp` to conceal differences.

## Retained and newly established blockers

### R2 — P1: disconnect does not stop active provider work

`test_repository_disconnect_stops_next_provider_turn` disconnects through the real owner API after first scripted provider response. It still observes **four turns total: three after disconnect**. Source callback in `live_defense/first_responder.py` checks OFF/job cancellation, but not repository or mapping revocation. Disconnect's queued repo-ID sweep does not cancel the running agent step. No source fix landed in this candidate.

Required: trusted repo/mapping linkage, cancellation of queued/waiting/running steps, and per-operation/final-persist revocation checks serialized with disconnect. Preserve already-incurred evidence/costs.

### R3 — P2: cached authorization survives failed fresh checks

The prior reconnect reproduction still gets **200** after a fresh installation check raises 404. The refresh helper catches the error and the cached access row is accepted. Three exact merged #540 connect regressions additionally return **201**, where 403/503 is required for removed repositories, deleted installations and unconfirmable installation context. The candidate lacks Adam's `verify_installation_access` helper/call.

Required: preserve latest-main fresh verification on connect and extend it to reconnect, including organization installations and outage/revocation cases. A GitHub-side permission failure must not reactivate Ari-side processing from stale cache.

### R4 — P2: repository picker exposes another tenant's connection ID

The unchanged picker joins repository rows globally by full name. Bob gets 404 for Alice's repository resource, yet `/github/repositories` returns Alice's ID as `connected_repo_id`. Other tenant/RLS tests pass; this metadata boundary still fails. No source bytes or write authority were obtained through this reproduction.

Required: authorize the joined connection by project/organization membership. Shared GitHub visibility is not Ari tenant membership.

### R5 — P2: abrupt worker death skips provider recovery bridge

`os._exit(71)` runs in the review's own child worker at the scripted provider boundary, after durable reservation. Lease expiry/reconcile produces **queued**, not **recovery_required**. The invocation ledger still prevents automatic second send; the missing guarantee is recovery-state/operational settlement. Catching `BaseException` in the original regression allows cleanup writes and therefore cannot prove this abrupt-death case.

Required: commit matching job uncertainty atomically with pre-send reservation, or reconcile from the ledger; settle matching effects with owner/attempt fencing and audited operator resolution. Do not guard pure canonical reads as external writes.

### C1 — P1: infrastructure credentials survive persistence and job API output

Exact latest-main `test_fail_scrubs_secrets_at_write_time` fails against candidate: `jobs.fail` writes raw error text. New independent `test_job_api_does_not_expose_infrastructure_credentials` passes a **synthetic** PostgreSQL DSN password through normal job failure, then receives that password unchanged in a **200** `/jobs/{id}` response. No real credential was read or printed.

The candidate lacks merged #530's write-time redaction and DSN/key-value redaction patterns. Token-only regexes do not scrub DSN passwords. Required: preserve latest-main error sanitization and apply it to all new lifecycle/history/recovery/diagnostic surfaces; test owner/member/outsider positive and negative cases.

### C2 — P2: merged project jobs/dead-letter API is missing

Four latest-main jobs-list tests fail (including role-coarsening/redaction consumers); the candidate lacks `GET /projects/{id}/jobs`. The tests encounter missing `items` on the error response. Source diff confirms deletion relative to latest main. This is an operational/consumer compatibility regression, separate from the credential exposure above.

Required: retain the merged endpoint, project filters, owner-only sanitized detail and coarse member errors while adapting to the expanded lifecycle states. Test cross-org isolation for the restored endpoint.

### C3 — P2: permanent commit failures and compare fallback regress

Two exact merged #540 tests fail: missing commit remains queued instead of completing with an explicitly skipped reassessment, and failed compare enumeration raises instead of falling back to signed payload commits. The candidate lacks upstream's permanent-failure classification and durable skipped-event handling. A delivery retry is not equivalent to an honest terminal outcome.

Required: reconcile upstream `auto_commits` behavior with candidate disconnect checks; retain no-work-after-disconnect while preserving scoped fallback/terminal evidence.

### C4 — P2: merged inline source-secret redaction is absent

Exact latest-main `test_mid_line_secret_values_are_redacted_without_breaking_parse` fails. A synthetic bare password in `dict(password=..., user=...)` survives `GitReader` normalization. Source diff shows candidate's older `_ASSIGN` regex lacks the merged mid-line delimiter branch. This is not proof that a real customer's secret was sent externally; it is direct evidence that the privacy boundary fails for the tested form.

Required: retain latest-main parse-safe mid-line redaction and its regression tests; do not fix it by deleting code structure or hiding parser failures.

### C5 — P2: credential-value quarantine misses secret-bearing telemetry

Exact merged #532 `test_secret_like_telemetry_is_quarantined` fails: production `secret_like_reason({"note": "password=hunter2"})` returns **None**. The candidate lacks upstream’s `_SECRET_VALUE` check. This establishes a detector-boundary failure; no end-to-end customer ingest or external disclosure is claimed by this direct unit test. Preserve the merged credential-value gate alongside existing key/email/bearer checks.

## Semantic compatibility with Adam's merged work

**Preserved and verified:** #535 tenant RLS, #533 capability-aware readiness/liveness/deploy pairing contracts, distinct heartbeat registry schemas, #558 storage/maintenance routes and their independent Bearer `OPS_API_TOKEN` protection, and the `ops_api` import alias from #567. Candidate X-Ops-Token status remains separate from upstream Bearer operator routes. Focused readiness/RLS tests pass.

**Not fully composed:** later upstream #530 release-gate/jobs/error-redaction, #531 intelligence redaction/audit, and #540 GitHub installation/commit lifecycle. The candidate was composed on `ee8b91e2`, not latest `2c825c4e`; the failing exact upstream regressions above establish substantive omissions. A claim that “no remaining code-level conflicts with Adam” is not supported.

During final verification main advanced from `0272616e` to `2c825c4e`, merging #570 expanded source/output redaction, #532 Defense Lab safety/quarantine, #538 first-user usability and #536 console/landing changes. Migration scripts are unchanged. The new safety regression files were also run: 20 failed/38 passed, including eight output-redaction failures, eleven source-privacy failures and one quarantine failure. These extend C1/C4 and establish C5. UI changes were inspected for overlap but no new exact-SHA browser signoff is claimed.

The latest-main regression files used in this audit were copied from pinned Git objects without changing assertions. New filenames prevent overwriting candidate tests; source SHA and paths are in evidence. Compatibility tests must accompany the fixes into the final composition.

## Per-PR merge approval matrix

“GO — tests/tooling only” approves the reviewed diff's purpose, **not customer release**, and does not execute any GitHub approval/merge. “HOLD” withholds approval for the exact standalone head; a corrected composition needs a new exact-SHA gate. Standalone heads are not interchangeable with the repaired integrated copies.

| Repository / PR | Exact head | Review decision | Reason / next gate |
|---|---|---|---|
| upstream #412 | `4ecd7558c20d676985294073d5a818a538bdf78c` | **HOLD for sequential landing** | Included prerequisite behavior passes in candidate; standalone head was not independently rebuilt against latest main and shared version allocation. Rebase/contract review and exact-SHA CI first. No new finding assigned to its feature logic here. |
| upstream #458 | `980352445f52f7043feeba97318a5d9f3478c389` | **NO-GO as-is** | Provider/job reservation/recovery contract remains incomplete; candidate-only queue-deadline/bridge integration must not be dropped. Fix R5 and preserve R2 revocation gates. |
| fork #1 reliability | `f2d911d785796f6d3aae2165c8981a042fec8ae1` | **NO-GO as-is** | Standalone still defines conflicting 0016 and old heartbeat registry; corrected 0018/worker_registry exists only in composition. Preserve latest-main job sanitization and coordinate R5. Emergency/OFF implementation passes in candidate. |
| fork #2 E2E | `247c23124ab167e8edf8cafac2d959f1d94b5ca0` | **GO — test-only diff** | Four changed files relative to declared integration base `dd530ae3`; own compatibility suite 8/8 and no xfails. Retarget/rebase to chosen final integration head and retain the new independent negative probes. Not approval of that base's production code. |
| fork #3 observability | `92e0009610659a1bab42f722e2990459ca48fd96` | **HOLD** | F6/F9 pass in composition; needs current schema/version and sanitization across new diagnostics, plus restored jobs-list semantics. No standalone consumer/build signoff inferred from candidate tests. |
| fork #4 hardening | `c7841e935e8cba10069bb2d5655bda5d154a3bb2` | **NO-GO as-is** | R2/R3/R4 and missing merged installation verification; standalone migration chain is still old 0016/0017. Bring over corrected 0019 and latest-main security behavior. |
| fork #5 deployment/ops | `c7c5336f79a9172b27e03d9570e7ae708b1f78b1` | **HOLD** | Candidate union passes readiness, but standalone ops router lacks newer upstream storage routes/semantics. Recompose on current main; do not overwrite Bearer ops routes with old file. |
| fork #6 onboarding | `7918bbee1e61a1469017c355493d1428efb87841` | **HOLD** | Depends on corrected hardening/reconnect semantics and current shared contracts; do not present stale cached access as completed authorization. |
| fork #7 release validation | `5f6827812768bfb291e49f70441180223da533d8` | **GO — rehearsal tooling only** | `deploy/release_readiness.py` is identical to candidate's executed script; 25/25 local checks. Base is fork #5, not latest main. Its GO output must remain scoped to checked properties, not overrule failing security/compatibility probes. Re-run on final SHA. |
| fork #8 integration | `070f75a9987658ef8b816cba412859f7b5c1c948` | **NO-GO** | Remaining R2–R5 plus C1–C5; not semantically current with merged Adam work. Conflicting and no remote checks reported. |

No GitHub review approval was submitted and nothing was merged/deployed.

## Required sequence before a new release decision

1. Freeze a recomposition on current main. Preserve its already-merged security, redaction, job API and installation/commit behavior rather than replacing whole files with older workstream versions.
2. Keep the proven 0017→0018→0019 chain and split registries; verify any existing fork-stamped staging lineage separately.
3. Resolve R2–R5 and C1–C5 with strict probes retained; test provider interruption between reservation/send/response and job settlement, plus disconnect during every active turn boundary.
4. Bring the standalone production PRs to those reconciled contracts/migrations, then land prerequisites → coordinated reliability/provider/hardening changes → observability/onboarding → ops → validation. Test-only PR #2 can follow its corrected base; tooling approval does not authorize deployment.
5. Run combined original, independent and transplanted upstream tests, contract regeneration, exact-SHA CI, frontend/browser and authorized staging evidence. Obtain fresh independent signoff. Current NO-GO remains until these actual failures are resolved.

Evidence and reproduction commands: `evidence/README.md`. The audit branch deliberately retains failing tests and is not a release candidate.
