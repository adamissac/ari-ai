# Independent security and integration review

## Decision

**NO-GO for merging any of the four reviewed candidates as the combined release.**
Two P1 and eight P2 findings are supported by source and executable evidence. No
P0 exploit, cross-tenant read bypass or autonomous infrastructure-control expansion
was demonstrated. The review does not infer safety from green individual PR CI.
Original PRs/branches remain unchanged and open. No paid provider calls, production
migration, customer enforcement or new RL experiment was performed.

Integration branch: `codex/first-responder-integration-review`. The source composition
is at 23d12cb3; review tests/evidence start at a5922307. Final branch SHA is recorded
in the handoff and final response (a report cannot contain its own commit hash).
This deliberately failing review branch is not a production merge candidate.

## Exact scope and provenance

Upstream main: see evidence/UPSTREAM_MAIN.txt (35e8b32c at capture).

- A: adamissac/ari-ai #458, **89a3debab24f27da8672a1f2b22239d916079b04**.
- B: m-alan08/ari-ai #1, **17c3ded021a48165bbdb03af014fb494133376c7**.
- C: m-alan08/ari-ai #2, **e187e9a20f5c9792da8d17371c0ef57c2573609b**.
- D: m-alan08/ari-ai #3, **b44b28aad69fb7775b6e9e0c5225b899a7446af1**.

Full captured diffs, review discussions and CI summaries are in evidence/pr-*.
DIFF_MANIFEST.json distinguishes exact original PR-base comparisons from composite
upstream-merge-base comparisons; the A review-thread snapshot retains resolution status. All
listed checks on the four captured heads were successful; C's live-provider job
was skipped. These are individual-head checks, not combined-branch CI. The review
branch has local integration evidence; remote full integration CI is not asserted.
Only documentation/generated-artifact/router/worker conflict composition is made
on this branch; substantive fixes are assigned to owners, not silently implemented.
See INTEGRATION_LOG.md for every conflict resolution.

## Independently rechecked six original A findings

All six reported remedies exist in the reviewed source and their focused tests pass
in the integrated run. This is narrower than approval of the entire execution path.

1. Canonical intelligence: `agent_execution.load_intel` selects LocalIntel only for
   explicitly configured fixture labels; `_canonical_intel` resolves authoritative
   SnapshotRef, project/repo/commit binding and verifies the materialized workspace.
   Tests: canonical adapter binding, missing index, cross-project fixture and
   snapshot mismatch. No fixture result is represented as canonical live evidence.
2. Cache charges: `_BackendGateway.cost_usd` includes cache creation, read and mixed
   usage without double-counting. The 10,000 cache-write/100 output Opus case charges
   $0.052 under repository pricing. This checks arithmetic, not actual provider bills.
3. Provider deadline: remaining runtime timeout reaches backend gateway and transport;
   retries refuse to begin when the remaining deadline cannot cover backoff/start.
   Deadline/no-start and retry-exhaustion tests pass. This does not establish a
   queue-wide deadline: F7 remains.
4. Diagnose scheduling: normal dispatch schedules Diagnose after executed Scout
   hypotheses, with no attempt-burning prerequisite retry. Concurrent/defer tests
   pass. The composition still bypasses lifecycle history for explicit deferrals: F4.
5. Partial provider failure: backend LLMError becomes runtime LLMUnavailable with the
   shared code, retaining earlier turns/usage/artifacts in ordinary failure paths.
   The partial transcript test passes. Process death before recording a response is
   a different uncertainty case: F1 remains.
6. Terminal redelivery: terminal invocation results are returned without repeating
   the loop; successful results resist later failed overwrites. Success/failure
   redelivery and concurrency tests pass. In-flight crash replay is not covered by
   this terminal-result guarantee, and cancellation can be overwritten: F1/F8.

## Prioritized defects

Each reproduction is executable on the pinned integrated branch. Tests under
`backend/tests/live_defense_e2e/test_independent_integration.py` assert the desired
property and intentionally remain failing. Reproduce with the repository test
runtime and `RUN_LIVE_LLM_EVAL=0`; no live key is needed. Raw output/XML is retained.

### F1 — P1: an uncertain provider request is automatically replayable

Pinned source: [backend/backend/live_defense/first_responder.py:998](https://github.com/adamissac/ari-ai/blob/89a3debab24f27da8672a1f2b22239d916079b04/backend/backend/live_defense/first_responder.py#L998).

Affected: **A + B**, Grok/Cursor and Devin reliability. Source: A
`backend/backend/live_defense/first_responder.py:998`; B `jobs.py:406` and
`execution.py:172`; backend runtime gateway has no JobContext effect/reservation hook.

Reproduction: `test_crash_during_provider_request_requires_recovery_before_replay`
sends a scripted provider request then raises a BaseException to model process death.
After lease expiry, reconciliation makes the job **queued**, not recovery_required;
its effect marker is null and a new worker may repeat the request. This failure is
observed before any real provider is contacted. Terminal-invocation idempotence does
not help because no terminal invocation was committed.

Root/consequence: provider charges and responses are external effects but the new
queue only protects declared effects. The actor can repeat billable work without a
settled cost/outcome or a durable attempt budget. No duplicate containment is claimed.
Required fix: agree on durable per-request identities and charge reservations; use
provider idempotency if supported, otherwise require explicit recovery for unknown
billable outcomes. Preserve partial attempt evidence. Guard billable calls/adapter
writes, not pure code reads or canonical-intelligence queries. A whole-loop blind
retry or declaring every read an external effect is not an adequate contract.
Regression: actual worker-loss fault after send/before response, concurrent claim,
OFF/revocation and original-deadline cases; no automatic second billable call until
uncertainty is resolved; ledger reconciles all attempts. C's scenario E currently
re-runs a physical loop while checking one logical invocation (line 373); correct
that claim and count provider calls/costs explicitly.

### F2 — P1: emergency stop and expiry are blocked by ordinary concurrency caps

Pinned source: [backend/backend/jobs.py:411](https://github.com/m-alan08/ari-ai/blob/17c3ded021a48165bbdb03af014fb494133376c7/backend/backend/jobs.py#L411).

Affected: **B**, Devin reliability. Source: B `backend/backend/jobs.py:411`.
`CONTROL_JOB_KINDS` exempts enqueue backpressure, but claim applies project/global
running limits to every kind. Real emergency-stop API payloads include project_id
(`backend/api/live_defense_controls.py:456`), so this is not a synthetic kind mismatch.

Reproduction: `test_emergency_stop_is_claimable_when_project_slots_are_full` claims
one normal job under project limit=1, queues priority-0 emergency stop, then tries
a separate stop worker: claim returns None. The same filter applies to rollback
and expiry jobs, whose real payloads also contain project_id.

Consequence: an available control worker cannot remove an active restriction until
ordinary work frees capacity. Priority does not bypass the WHERE clause. This test
does not prove all workers can be preempted; separate emergency capacity is required.
Fix: reserved emergency/rollback/expiry capacity or narrowly scoped claim exemptions
with their own limits, never an unrestricted bypass for new apply operations.
Regression: saturate project AND global caps, enqueue genuine emergency-stop,
rollback and expiry paths, verify bounded cleanup delay and no privilege expansion.

### F3 — P2: normal completion accepts an expired lease

Pinned source: [backend/backend/jobs.py:541](https://github.com/m-alan08/ari-ai/blob/17c3ded021a48165bbdb03af014fb494133376c7/backend/backend/jobs.py#L541).

Affected: **B**, Devin reliability. Source: B `backend/backend/jobs.py:541`.
Reproduction: `test_complete_rejects_expired_lease_without_waiting_for_reconciler`
claims a job, expires its lease, then completes with the old owner: returns True.
Root: completion checks owner/status/cancel but not lease expiry or a current lease
fence. An already-reclaimed different owner is checked; no overwrite of a newer
owner was demonstrated. The missing case is the interval before reconciliation.
Consequence: documented lost-lease completion guarantees are weaker than stated.
Fix: define the completion fencing contract explicitly; enforce live lease/attempt
for normal completion, retaining any intentional late uncertain-effect settlement
as a separate audited outcome path. Regression: expired lease before reclaim,
concurrent reclaim/heartbeat, cancelled and deadline cases; no false claim that this
test demonstrates an unauthorized infrastructure action.

### F4 — P2: dependency deferral bypasses lifecycle history

Pinned source: [backend/backend/jobs.py:161](https://github.com/adamissac/ari-ai/blob/89a3debab24f27da8672a1f2b22239d916079b04/backend/backend/jobs.py#L161).

Affected: **A + B** integration, Grok/Cursor + Devin. Source: integrated
`backend/backend/jobs.py:576`; A added defer, B added transition/history contracts.
Reproduction: `test_dependency_deferral_is_recorded_in_lifecycle_history` defers a
claimed job. DB status becomes queued but the last history event remains running.
Root: direct SQL status rewrite bypasses transition/record_event, cancellation,
deadline and effect-state precedence. A's current deferrals occur before its provider
loop, so a post-effect replay through this path is not claimed as reproduced.
Fix: implement an explicit deferral transition with event/attempt semantics and
state guards, ideally durable prerequisites. Regression: history matches state,
no retry burn, deadline/cancel precedence and no deferral after uncertain effects.

### F5 — P2: OFF cancellation misses new waiting jobs

Pinned source: [backend/backend/live_defense/modes.py:187](https://github.com/adamissac/ari-ai/blob/89a3debab24f27da8672a1f2b22239d916079b04/backend/backend/live_defense/modes.py#L187).

Affected: **B + A consumer**, Devin reliability with Grok/Cursor. Source:
`backend/backend/live_defense/modes.py:187` filters only queued/running.
Reproduction: `test_off_marks_waiting_first_responder_jobs_cancelled` creates a real
first-responder dependent job in waiting, invokes the cancellation helper used by
the real OFF API: status remains waiting and cancel_requested=false.
Consequence: previously queued work survives OFF and can become runnable after a
prerequisite completes; the handler still rechecks OFF, so execution while OFF is
not claimed. Re-enabling monitoring can revive old uncancelled work.
Fix: cancel all relevant nonterminal waiting jobs and define recovery-required
cancellation without erasing effect evidence. Regression: OFF via API, dependency
settlement, OFF→ON, recovery retry refusal, and independently authorized controls
remain untouched.

### F6 — P2: stopped/recovery work is displayed as in progress

Pinned source: [backend/backend/api/live_defense_investigations.py:140](https://github.com/m-alan08/ari-ai/blob/b44b28aad69fb7775b6e9e0c5225b899a7446af1/backend/backend/api/live_defense_investigations.py#L140).

Affected: **D + B**, Devin observability/reliability. Source: D
`backend/backend/api/live_defense_investigations.py:140`, plus lines 82/470/531;
frontend `components/live-defense/executions.tsx:27` lacks new-state tones.
Reproduction: parameterized `test_observability_marks_nonrunning_jobs_as_not_in_progress`
sets a queued invocation's job to timed_out or recovery_required. The job view
contains the true state but timeline final_state remains in_progress in both cases.
Root: final state considers invocation status only; diagnostics/latency/waiting
queries enumerate old queue states. Waiting jobs and recovery counts are omitted.
Fix: define canonical precedence between job/invocation/decision states and expose
waiting, timed_out and recovery_required explicitly without presenting them as
confirmed compromise. Regression: list/timeline/diagnostics and UI for each new
state, partial failure, cancelled and unresolved-effect records; no invented latency.

### F7 — P2: first-responder jobs have no durable overall deadline

Pinned source: [backend/backend/live_defense/first_responder.py:764](https://github.com/adamissac/ari-ai/blob/89a3debab24f27da8672a1f2b22239d916079b04/backend/backend/live_defense/first_responder.py#L764).

Affected: **A + B**, Grok/Cursor + Devin. Source: A
`backend/backend/live_defense/first_responder.py:764` enqueue has no deadline_s;
run_investigative creates a fresh per-attempt timer. Provider timeout fix is real.
Reproduction: `test_first_responder_step_has_a_durable_queue_deadline` ingests through
the public API and drains only shadow/orchestration: the real Scout job has
`deadline_at=None`. B's pending/retry deadline logic cannot bound it.
Fix: persist the original incident/investigation deadline, propagate it through
queueing, dependency waits, retries and provider calls. Never reset on redelivery.
Regression: queued backlog, long Scout prerequisite and worker recovery under one
absolute deadline; exhausted budget/deadline must not start another provider call.

### F8 — P2: final-submit race overwrites OFF cancellation

Pinned source: [backend/backend/live_defense/first_responder.py:734](https://github.com/adamissac/ari-ai/blob/89a3debab24f27da8672a1f2b22239d916079b04/backend/backend/live_defense/first_responder.py#L734).

Affected: **A**, Grok/Cursor. Source: A `first_responder.py:735` permits an executed
result to replace a cancelled terminal invocation; final persistence at 1008 checks
OFF only when committed.status is not executed. Runtime loop accepts submit without
another cancellation check after the provider response.
Reproduction: `test_off_during_final_submit_cannot_upgrade_cancelled_invocation`
sets OFF through the real API while the scripted provider returns Scout's valid
submit. OFF succeeds; final invocation is executed rather than cancelled.
Consequence: stale completion erases cancellation and the evidence chain misstates
what was accepted after revocation. No new control or post-OFF provider call is
asserted. Fix: recheck cancellation/mode/lease before accepting final output and
persist partial transcript/charges without upgrading cancelled state. Regression:
barriers around final response and final DB commit, both OFF and job cancellation;
terminal success before cancellation may remain immutable, with ordered provenance.

### F9 — P2: A's schema test prevents additive D composition

Pinned source: [backend/tests/test_live_defense_phase7c.py:130](https://github.com/adamissac/ari-ai/blob/89a3debab24f27da8672a1f2b22239d916079b04/backend/tests/test_live_defense_phase7c.py#L130).

Affected: **A + D**, shared-contract owners. A
`backend/tests/test_live_defense_phase7c.py:130` asserts exactly 0.22.0. Integration
correctly preserves A models plus D DTOs under 0.23.0 and regenerates aggregate JSON/TS;
106 shared tests and freshness checks pass, but A's exact-version test fails.
Fix: test the required versioned capabilities/compatibility rather than a permanent
exact intermediate version, or update it explicitly in the D integration/rebase.
Regression: A records, D view and generated TS/JSON roundtrips together. Do not drop
A types or downgrade 0.23 to make the assertion pass. This is a test/merge gate,
not evidence of a demonstrated wire-decoding exploit.

### F10 — P2: C's activated deadline compatibility test uses mismatched clocks

Pinned source: [backend/tests/live_defense_e2e/test_exec_reliability_compat.py:105](https://github.com/m-alan08/ari-ai/blob/e187e9a20f5c9792da8d17371c0ef57c2573609b/backend/tests/live_defense_e2e/test_exec_reliability_compat.py#L105).

Affected: **C**, Devin E2E. Source: C
`backend/tests/live_defense_e2e/test_exec_reliability_compat.py:105`.
Reproduction: existing test fails on integration. Python utcnow() is written inside
a PostgreSQL transaction whose now() was fixed earlier; reconcile's SQL predicate
can see that deadline as future. It is not evidence the runtime never times out.
Our separate `test_deadline_compatibility_with_database_clock` uses DB now()-1 second
and passes. Fix: use an unequivocally past DB timestamp or commit a controlled clock
fixture; run these formerly skip-gated tests whenever B is composed. Regression:
full E2E+compatibility tier repeatedly passes without sleep-based timing assumptions.

## Cross-PR compatibility matrix (also rendered in the audit canvas)

- **A/B — blocked:** shared worker definitions must be composed; paid-call uncertainty,
  durable deadline, deferral history and waiting cancellation remain unresolved.
- **A/C — partial:** scenario and security-fix tests pass on A's newer head; C was
  stacked on an older A lineage. Rebase C onto the approved A/B integration, preserve
  A's final security fixes and distinguish physical attempts from logical records.
- **A/D — test blocked:** real execution/view shapes coexist and browser tests pass;
  additive version must remain 0.23 and A exact-version test must be reconciled.
- **B/C — blocked:** generic queue compatibility tests activate, exposing F10;
  existing crash assertions do not prove unknown provider effects cannot replay.
- **B/D — blocked:** new queue states are not incorporated into timeline/diagnostics.
- **C/D — happy path passes:** three browser tests pass, but stopped/recovery paths
  need the new regressions. Happy-path rendering is not distributed-failure proof.

## Migration and schema assessment

B is the only reviewed PR adding **0016**, down_revision=0015. A stores execution in
existing invocation JSONB; C adds tests; D adds DTOs, no migration. No duplicate
migration ID among these four pins. Three migration tests pass: single head,
parallel-head upgrade/downgrade and independent populated 0015→0016→0015→0016 preserving
queued/running/succeeded/cancelled jobs and backfilled project IDs. This does not
validate a rolling production deployment or downgrade with real uncertain effects.

Deploy 0016 before running code that selects its new columns; mixed old/new workers
must be drained or compatibility explicitly tested. Old code does not understand
new status values and there is no automatic guarantee for all existing consumers.
Audit/backfill project identity and inventory active/uncertain jobs before deployment.
Do not downgrade away unresolved effect records without an approved operational plan.

Schema order: current main 0.21; A 0.22; D 0.23. B/C claim no new independent shared
schema. Open #412's reserved 0.20 must not later downgrade the registry. Combined
canonical exports were regenerated from the union of models, not chosen from one
side's stale generated aggregate. Strict extra-forbid consumers are not universally
forward-compatible; coordinated generated-type rollout and actual payload tests are
required. D explicitly strips/parses optional execution view fields; those paths pass.

## Trust-boundary results and limits

Observed positives: project-scoped read APIs deny cross-project access in tests;
owner role protects recovery/mode changes; mapped snapshot identity mismatches and
revoked mappings fail closed; canonical intelligence is bound to project/repo/commit;
Scout/Diagnose keep read-only tool allowlists; model injection cannot widen Probe,
Patch, Verify or grant authority; typed execution remains unverified; handoff confirm
refuses completed_unverified; artifact reads check digest; controls retain independent
authorization and no first-responder auto-execute path was introduced. Ordinary
provider errors retain partial evidence and charged usage. Concurrent claims and
terminal redelivery tests pass. These are synthetic/local evidence, not live-provider,
Docker isolation, 24/7 uptime or real incident-response effectiveness claims.

Unresolved: F1/F2 block financial/recovery and emergency-control guarantees; F3–F8
weaken lifecycle, cancellation/deadline and observability claims. Provider usage and
model identity are trusted metadata, not independently audited invoices. Owner
attestation of deployed commit remains a trust assumption. Browser tests run with
scripted providers and local owned fixtures. Docker was unavailable locally; 23
security-agent tests are skipped for Docker/opt-in conditions. Paid live tests stay
disabled. Individual PR CI's Docker results are captured but not relabeled as our
combined local Docker execution. No customer or remote infrastructure was probed.

## Executed integrated verification

- Backend: **407 passed, 2 failed, 8 skipped** (schema assertion and C clock test).
  Relevant RL tests initially skipped for absent dependencies; separate execution
  after exposing compatible existing dependencies: **8 passed**.
- Security agents: initial missing SDK produced two environment errors; after installing
  the lockfile SDK in an isolated directory: **593 passed, 23 skipped**. No live sandbox
  request was made by the SDK unit checks.
- Shared: **106 passed**; generated export freshness and examples passed.
- Migrations: **3 passed**, including populated upgrade/rollback proof.
- Scripted E2E smoke: **2 passed**; failure tier: **8 passed**. Full scenarios A–H and
  compatibility tests ran in the combined backend run; F10 is its failing compat case.
- Independent regressions: **9 failed, 1 passed**, deliberately retained. The two
  observability parameters are one finding. These are not hidden with xfail.
- Frontend: **344 tests /80 files passed**, lint/typecheck passed; production build
  passed after rerunning with required local process permissions.
- Transport: **35 passed**. Playwright: **3 passed** against real localhost API,
  PostgreSQL/queue/runtime/artifacts/Next with scripted models.
- Python Ruff and format: passed (183 backend/shared files); configured mypy:
  **40 source files passed**. This configured scope is not strict coverage of every
  backend/agent module. No blanket whole-repository strict-type claim.

Raw logs, JUnit XML, captured pins and TEST_RESULTS.json are in evidence/. Initial
setup failures (embedded PostgreSQL cache permission, missing SDK, RL subprocess
path, sandboxed build) were environment constraints, not counted as product defects;
the successful reruns above retain their actual scope. Overlapping suites are not
summed into a misleading unique total.

## Owner follow-up and safest merge sequence

1. **B — NO-GO**, 17c3ded0: Devin reliability fixes F2/F3, composes F4/F5, agrees
   per-request uncertainty and overall deadline with A. Re-run real queue lifecycle,
   emergency-capacity, cancellation and recovery tests. Migration 0016 is unique and
   upgrade-tested, but no production migration approval follows from that fact.
2. **A — NO-GO**, 89a3deba: Grok/Cursor fixes F1/F7/F8, integrates reviewed B worker
   contract and maintains the six verified remedies. Require canonical context,
   all-attempt accounting, final-submit cancellation and crash-before-response tests.
   No Probe/Patch/Verify privilege expansion, no customer enforcement.
3. **C — NO-GO**, e187e9a2: Devin E2E rebases onto the exact approved A+B heads;
   fixes F10, adds provider-loss and cancellation-boundary tests, corrects scenario E
   physical-attempt claims, and demonstrates full/smoke/fault/browser tiers without
   skip-gating the B contract checks. Live tests remain separately authorized.
4. **D — NO-GO for the combined release**, b44b28aa: Devin observability fixes F6,
   coordinates F9, tests failed/timed_out/recovery/waiting states and actual persisted
   A records; retains final schema 0.23 and generated freshness. It can be developed
   and tested on old main independently, but that does not approve its compatibility
   with B or a D-first/A-downgrade sequence.

Recommended sequence after fixes: **B foundation → A reviewed execution integration
→ C rebased evidence → D updated observability**. A/B fixes can be a coordinated
review set; do not deploy A paid execution while its B uncertainty adapter is absent.
C may be squash-split into tests only after dependency ancestry is understood, never
merge its old embedded A changes over the approved A head. All four need new pinned
heads, fresh combined CI, zero unresolved P0/P1, closure or explicit owner acceptance
of remaining P2s, shared owner review, migration rollout plan and independent security
signoff. The current combined regression failures must not be waived by green
individual PR CI. **No original PR was merged or closed.**

Final remote recheck: all four PRs remain OPEN at the exact reviewed SHAs. See evidence/FINAL_REMOTE_STATE.json.

Evidence hygiene: security-agent JUnit stdout contains a synthetic key-redaction
fixture; private-key markers and secret-shaped parameter IDs in retained XML were redacted.
GitHub push protection caught synthetic Slack parameter IDs before publication;
the unpushed report commit was amended without bypassing the protection. Test outcomes are
unchanged. No real provider key was supplied to these test runs.
