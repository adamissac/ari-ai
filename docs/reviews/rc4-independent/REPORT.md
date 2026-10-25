# Independent RC4 security and merge-readiness review

**Verdict: NO-GO for upstream merging and customer deployment.** Known F1–F10 and N1–N7 fixes pass on the pinned product, but a newly reproduced P2 credential-redaction gap and an unresolved latest-main composition prevent overall security/release signoff. No new P0/P1 was established. No production edits, feature fixes, merges, deployments, live provider calls or GitHub approvals were made.

## Exact scope

- Production candidate: `6a72949efa7c0a2d3233eb6884bb7a23dfe71ced` (RC4).
- Observed fork PR #8 head: `cdf9231be4320810701675cfe469fe4c65d85b50`.
- Canonical main fetched for comparison: `e41c9dc22e6536463cdab9be6a2a4cd76302c866`.
- Original independent test source: `abf6b316b1de2fea9a8ac8c89a79a7368900145a`.

The head after RC4 changes `.github/release-review/`, `.github/workflows/codex-release-review.yml` and coordination files. It is **not solely prose**. Those automation changes are outside this product audit and receive no security approval here. No newer production code was substituted for RC4. Missing paid review credentials are not a product finding.

## Resolution matrix

Each entry below is PASS for the original requirement on RC4, based on production inspection and the retained independent executable assertions. This does not certify the unresolved landing tree.

- F1 PASS — unresolved billable attempts block automatic replay; process-death and recovery probes pass.
- F2 PASS — emergency-stop jobs remain claimable with ordinary project capacity full.
- F3 PASS — expired leases cannot complete before reconciliation; attempt fencing retained.
- F4 PASS — dependency deferrals retain lifecycle history.
- F5 PASS — OFF cancels waiting first-responder jobs.
- F6 PASS — nonrunning and recovery states are not displayed as running.
- F7 PASS — durable queue/investigation deadlines survive requeue/recovery; no xfail.
- F8 PASS — OFF during final submission cannot upgrade a cancelled invocation.
- F9 PASS — integrated schema is the string `0.26.0`, not a tuple; contract/version checks retained.
- F10 PASS — deadline behavior uses database-clock-compatible comparisons.
- N1 PASS — finalization takes the repository/mapping locks and rechecks revocation before commit. The competing-transaction lock test and original disconnect-after-read test pass.
- N2 PASS — reconnect explicitly verifies the recorded target installation, independently of a healthy personal installation; stale/failed refresh denies.
- N3 PASS — claim and reconcile both inspect unresolved invocation ledger attempts; operator retry closes the stale attempt in the same locked job transaction. Fast-reclaim and abrupt process-death tests pass.
- N4 PASS — reasons/details are scrubbed at write and read. Real legacy raw rows are scrubbed for the viewer; the unrelated-user 404 control passes.
- N5 PASS — distinct 0018 execution-reliability and 0019 disconnect revisions, correct parent chain and one real migration head.
- N6 PASS — actual sequential schema progression is `0.22 → 0.23 → 0.23 → 0.24 → 0.25 → 0.26 → 0.26 → 0.26`; original type/monotonic assertions pass with pinned transfer inputs.
- N7 PASS — both nonliteral-expression artifact byte-equality tests and the parseability reproduction pass; ordinary quoted assignment/token/DSN scrubbing controls pass.

R2–R5 remain covered: disconnect stops subsequent provider turns and rejects late success; reconnect checks the exact renewed grant; the repository picker does not reveal another tenant's connected row; uncertain provider outcomes require operator disposition. No live provider idempotency/billing guarantee is inferred from scripted providers.

Source review confirms these are implementation fixes rather than assertions accepting failures: `first_responder.py:1259–1340`, `services.py:345–383`, `routes.py:483–646`, `jobs.py` unresolved-ledger claim predicate, and `execution.py` history/read and recovery disposition. Four original independent files are byte-identical to the prior audit (hashes in `evidence/strict-provenance.json`). Only immutable Git SHA/path inputs in migration/transfer probes were refreshed by the trusted runner. No assertion, xfail or skip was added to hide a failure.

## N8 — P2: literal credentials survive “redacted” diff artifacts

Production references on RC4:

- [redaction.py:44](https://github.com/m-alan08/ari-ai/blob/6a72949efa7c0a2d3233eb6884bb7a23dfe71ced/backend/backend/redaction.py#L44): `_CODE_KV_PATTERN` handles simple quoted assignments but misses quoted mapping keys and annotated assignments.
- [artifacts.py:102](https://github.com/m-alan08/ari-ai/blob/6a72949efa7c0a2d3233eb6884bb7a23dfe71ced/backend/backend/artifacts.py#L102): diff writes use that redactor and unconditionally label the artifact redacted.
- [routes.py:1587](https://github.com/m-alan08/ari-ai/blob/6a72949efa7c0a2d3233eb6884bb7a23dfe71ced/backend/backend/api/routes.py#L1587): the project-authorized artifact download returns the retained bytes.
- `security-agents/security_agents/host_adapter.py:631` and `backend/backend/host.py:538`: real patch-diff producers use this public artifact path. The separate sealed-diff path remains inaccessible through this endpoint.

Reproductions use only synthetic credentials:

```python
settings = {"password": "review-only-dict-password"}
password: str = "review-only-typed-password"
```

For each form, two independent assertions fail: the real `ArtifactStore.put_text(..., kind=ArtifactKind.diff)` retains the literal despite `redacted=true`, and a real project **viewer** gets HTTP 200 containing that literal through `/api/v1/artifacts/{id}`. Before the disclosure assertion, an unrelated user gets 404. Thus this is a same-project sensitive-data disclosure / false-redaction guarantee, **not** an observed cross-tenant authorization bypass. Public diff content should redact secret literals while sealed verified delivery retains exact original bytes behind its existing boundary.

This gap is newly identified by this review; the regex limitation predates RC4, and the N7 repair is not claimed to have introduced it. Do not restore the generic free-text matcher to code, which would reopen N7. Add syntax-aware literal handling and retain nonliteral/byte-integrity controls. No fix was made by this reviewer.

## Independent execution and limitations

Tests ran in disposable GitHub Docker containers: read-only candidate source and pinned independent fixture mounts, no provider/API/GitHub credentials inside, dropped capabilities, 4 CPU/8 GiB limits, internal-only disposable PostgreSQL, no outbound candidate network. The controller never executed candidate code on the host.

Final [run 40202085130](https://github.com/m-alan08/ari-ai/actions/runs/40202085130), controller `78dc57bc`: **182 passed, 5 failed, 0 skipped, 0 test errors** in 32.87 s. Four failures are N8 (two store checks plus two real API checks). One is the separately copied latest-upstream protected-test compatibility probe: it reaches `VerifyEvidence(..., candidate_id=...)` and raises TypeError because that constructor field is absent on RC4. This is **INCONCLUSIVE for the final verifier verdict**, a real interface incompatibility; it is not evidence that Verify approved a bad patch. The preceding tampered-test detection assertions pass. The two current-upstream hourly/daily reset probes pass. Current spend-policy and every newer Verify behavior are not thereby certified.

The result collector also reports a cleanup error removing container-owned result files on the disposable runner. This fail-closed harness error is retained; the job is not called green. It does not change the recorded test assertions or establish a product vulnerability. The disposable runner terminates after artifact upload.

Earlier runs are retained, not hidden: run 40201574838 had 182 passed / 1 compatibility failure and a read-only E2E result-directory teardown error; run 40201839194 fixed only that writable output mount and had 182 passed / 3 failures (two initial N8 cases plus compatibility). The final run added API-level reproductions. Original security assertions stayed unchanged through all runs. No selective successful rerun replaces a failing result.

Migrations ran against real PostgreSQL: fresh upgrade/rollback/re-upgrade, populated 0017→0019→0017→0019, single head, parallel branch upgrade/downgrade, and the **actual current-main migration scripts upgrading into RC4** pass. Current main adds no migration revision since eea084bc. The candidate and complete old-base transfer tree have identical migration files, ending at 0019. This validates database compatibility, not the unresolved latest-main application union.

## Verified original GitHub CI

GitHub's check-runs API confirms **21 successful checks and one skipped `live` check bound to exactly RC4**. Raw API evidence and execution-summary excerpts are retained. Key actual executions:

- Backend/shared/workspace: 1211 passed, **16 skipped**; separate RL integration 4 passed.
- Security agents: 646 passed, **23 skipped**; Docker boundary groups 11 passed and 2 passed.
- Frontend unit: 365 passed in 86 files; Playwright: 49 passed.
- Live-defense deterministic full: 26 passed, 1 optional live test skipped, 21 deselected; fault 8 passed; smoke 2 passed.
- Lint, generated contracts, builds, audit/gitleaks and other listed checks succeeded.

These counts overlap and are not summed. “21 green checks” does not mean zero skipped tests. Backend skip reasons include optional live providers/rehearsal, separately provisioned Docker/RL suites, and specialist cache prerequisites. The security job's summary gives 23 skips without per-test reasons; their full individual coverage is therefore not asserted. The required original independent security/migration rerun above had zero skips. Live-provider/customer smoke was not run. Same-SHA green owner CI does not override the new independent failures.

## Latest upstream semantics and real merge equivalence

Eight actual transfers were pinned and composed with `git merge-tree --write-tree`, preserving both parents in synthetic review-only commits at each step. No conflicted tree was accepted or manually resolved. Full transcripts and SHAs: `evidence/sequential-composition.json`.

On base `eea084bc87ac6ca94f578073251c478655b09366`, all eight steps compose cleanly:

1. S1 #412 transfer `0e2d26c232658a38261d0ce68617f15ba8661566`.
2. S2 #458 transfer `40f1e333fbaf5ee2a00117e26d3b19d4b0e4f7ee`.
3. Reliability `1ae4952e7c12dff049d9939e9a976fd0d57f1f0f`.
4. Observability `286f20af7197db9fa230438419bb3e3fca43aee5`.
5. Hardening `da14512608626512415ba2aafdf207c1b1a16747`.
6. Onboarding `36ebc704fcc2a5dc0a4f4f77b7c0f352aca6cb15`.
7. Ops `bb09759136fcc97963f6eeadbd863b35d8ef9cac`.
8. Validation `283ad2d49c9a0a76fa4f9c27a5629eb1b629465e`.

The resulting production tree matches RC4, preserving the integrated N1–N7 fixes. A full candidate-vs-S8 Git diff has **only seven coordination-message differences**, no application, frontend, migration, test or deployment differences. The old `transfer/sequential-manifest` 308f45e4 is stale; it is not the proof used here.

On current main `e41c9dc2`, the sequence **stops at S1** on generated JSON/TS contract conflicts. A direct current-main/RC4 merge also conflicts in `api/routes.py`, `api/ops.py`, `auto_commits.py`, `settings.py`, generated contracts, and planning/changelog files. There is no clean proposed landing commit to test. Post-composition CI is **UNVERIFIED**, not presumed green.

Preserve and reconcile these newer upstream changes rather than copying the RC4 tree over main:

- #598 App-installation-token live analysis/settings and current repository authorization/UI flows; #623 onboarding and #624 console integration.
- #592 default pull-request delivery; #608 delivery status; #616 stale-base/already-applied handling and sealed Verify provenance.
- #601 protection for all pre-existing tests, #618 recipe-declared new tests/runner-tamper boundaries, #626 fail-closed runner-config discovery. RC4's old constructor is a concrete compatibility seam.
- #593 reviewer settings/automatic PR review semantics and their `auto_commits`/tenancy contract union.
- #605 rolling spend-reset accounting, #607 manual versus automatic quotas/read limits. Passing two reset probes does not prove this whole policy union.
- #621 retention/referenced-snapshot and destructive-pruning guards, ops/settings/deployment integration; frontend design/route changes #619/#622/#623/#624.

Open overlapping work at final capture: canonical #629 (Verify hook-attribute/rootdir-symlink guards), #630 (scope-duration UI copy), #631 (cloud health handoff), and #579 (production rehearsal/NO-GO launch record). These are not treated as merged or independently approved here. Recheck #629 if it lands before recomposition.

There are no post-base `jobs.py` or `worker.py` commits in the compared main range; generic queue/worker code drift is not invented as a separate blocker. Their interactions with new quota/retention/delivery paths still require landing-tree tests. Missing newer functionality is ordinary version drift unless it removes a security guarantee; unresolved conflicts and absent post-union evidence are the merge blockers.

## Exact PR-by-PR decision (no approvals submitted)

Exact original PR heads remain distinct from cumulative transfers. Decisions are for landing on current canonical main, not their older fork bases:

- Canonical #412 `4ecd7558c20d676985294073d5a818a538bdf78c`: **HOLD**. Use/reconcile S1 implementation against current contracts; original PR is not the reviewed cumulative transfer.
- Canonical #458 `8396e836866e33ebc34a402a7c8bd0eb6bc769d8`: **HOLD**. Preserve reviewed provider/finalizer unions through S2; no latest-main result exists.
- Fork #1 `a23964e10307b6979f80562d542ca48a15460d5a`: **NO-GO** for release signoff pending N8 correction and current-main composition. Provider recovery fixes pass integrated; this is not a blanket recovery failure.
- Fork #2 `247c23124ab167e8edf8cafac2d959f1d94b5ca0`: **already MERGED in fork**; retain strict tests, no new merge approval.
- Fork #3 `c30c631d99b192e528345baf2aba8e97b047bd94`: **HOLD**; integrated isolation/history behavior passes, current-main contract/API union unverified.
- Fork #4 `65e33986fda0f0cf73b2f64ee1f7a4d7fa93338b`: **HOLD**; N1/N5 pass in composed transfer; preserve finalizer glue and 0019 when rebasing.
- Fork #6 `9317b339cc006be88a4396a363f674151c9f8e47`: **HOLD**; N2 passes integrated, reconcile newer App/onboarding flows.
- Fork #5 `c7c5336f79a9172b27e03d9570e7ae708b1f78b1`: **HOLD**; ops/settings/retention conflict union and final deployment pairing need tests.
- Fork #7 `16fa812228e04e52e59d773a207075f781f51a17`: **HOLD** until it validates the new final composition, including N8.
- Fork #8 product `6a72949e`, head `cdf9231b`: **NO-GO** for canonical landing/customer release; known-findings-only security GO is limited to pinned RC4.
- Fork #9/#10 automation installers: **outside RC4 product signoff**; do not enable paid review as a prerequisite for this manual audit.

The dependency order remains current main → reconciled S1 → S2 → reliability → observability → hardening → onboarding → ops → validation. It is proven only on the old base today. No current step has final sequential merge approval.

## Separate verdicts and minimum remaining work

- **Known F1–F10/N1–N7 security: GO on RC4 only.**
- **Overall security/customer deployment: NO-GO**, N8 remains reproducible.
- **Upstream merging: NO-GO**, latest-main union conflicts and has no tested landing SHA.
- **Isolated staging release signoff: HOLD.** Synthetic, credential-free fixture reproduction is appropriate; it is not customer/readiness approval. A staging rehearsal with real secrets must account for N8 and use the final reconciled build.

Minimum: fix N8 without reopening N7 or altering sealed original diffs; reconcile/recompose all eight steps against pinned current main and regenerate contracts; preserve the listed upstream security/delivery/quota/retention semantics; adapt callers through real production contract changes rather than weakening assertions; run the original strict probes, N8 API controls and current-upstream suites on that exact landing SHA; obtain passing same-SHA required CI, then staging/provider/operational evidence for the final deployment. Full security-suite skipped-test coverage remains explicitly bounded. The independent report runner's result cleanup should also be repaired before claiming an unattended green audit.
