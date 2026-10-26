# Independent release check — 36bd05ee

**GO for the exact reviewed integrated candidate, as a technical merge-readiness recommendation.** Original security requirements pass, same-SHA product CI passes, current main is included and direct landing is conflict-free. No new defect was established. This is not a GitHub approval submission, merge, deployment or customer-enforcement authorization.

## Exact reviewed state

- Candidate: `36bd05eeebd101064175f33726934ead35515b4b`.
- Canonical main: `ba4ada0d2387a4f6fcb3b0adbfc65bfaf934ce25`, fetched again after the tests; unchanged.
- Independent regression source: `abf6b316b1de2fea9a8ac8c89a79a7368900145a` plus retained N8/N9 and upstream #629 probes.
- Direct main/candidate merge-tree: `62c66fcd219ff6202e3351314808942cc6426763`, identical to the candidate tree; exit **0**. Main is an ancestor of the candidate.

This review stays on the requested immutable SHA. It does not silently approve a newer branch tip or a reconstructed stack with different production bytes.

## Independent verification

[Run 40291575442](https://github.com/m-alan08/ari-ai/actions/runs/40291575442), controller `f6883835`, checks the actual candidate, not a hypothetical landing:

**194 passed, 0 failed, 0 skipped, 0 errors; receipt exit 0; GitHub job success.**

Original **F1–F10 / N1–N9: PASS**. The newer #629 imported-hook and symlinked-rootdir/config protections also pass. Covered boundaries include provider-attempt replay/crash/operator recovery, emergency capacity, lease/deadline fencing, OFF cancellation, transactional disconnect/finalization, exact-installation reconnect, tenant isolation, legacy history redaction, source/diff integrity and migration/schema ordering. Real database upgrade/downgrade/populated migration checks pass, ending at **0019**. No new P0/P1/P2 finding was established in the checked scope.

Tests execute in bounded, network-restricted Docker containers with pinned read-only candidate/fixture mounts and disposable real PostgreSQL. Providers are scripted; live-provider/customer behavior is not inferred. No candidate code runs on a credentialed host. No OpenAI/Devin/provider key or paid request is needed.

The documented #607 GET-rate-limit fixture adaptation changes only the configured read-limit input; response/count assertions remain unchanged. Independent split read/write controls pass. No assertion, xfail or skip was altered to hide a failed security outcome. The one-off workflow is archived after capture; no automatic audit retry loop is installed by this report.

## Frontend reconciliation inspected

The prior #638 conflict is resolved in real production commit `d8c5ff38`, incorporated in this candidate. Relative to current main:

- `frontend/components/project.tsx` preserves the classic shell and adds one **Onboarding** entry to the More menu.
- `frontend/tests/unit/project-navigation.test.tsx` preserves main's assertions and adds the matching onboarding destination expectation.
- `frontend/tests/e2e/demo-recovery.spec.ts` is byte-identical to current main.

The previous conflict was not cleared by removing these tests or replacing them with weaker assertions. Integrated release/onboarding/live-defense frontend additions remain in the candidate. No backend/security/shared production change occurred since the preceding b6d security pass; the actual frontend union and this exact source were rechecked, not assumed from old CI.

## Same-SHA CI independently confirmed

The GitHub check-runs API reports **24 successful checks, one failed paid-audit report and two skips**. The failed report reflects an unavailable paid Codex audit; optional paid Codex/live-provider checks are skipped. Those are not product vulnerabilities and do not invalidate this manual independent review. No provider/account setup was assumed.

Actual executed suite logs on this exact SHA show:

- Backend/workspace: **1317 passed, 16 skipped**; separate RL integration **4 passed**.
- Security agents: **839 passed, 23 skipped**; real Docker groups **11 passed** and **2 passed**.
- Frontend: **427 unit tests in 99 files**, and **51 Playwright tests**, passed.

Required product jobs including backend, RL integration, security agents, code intelligence/review, frontend unit/browser, containers, generated-contract checks, lint and secrets checks report success. Counts overlap; they are not summed. Full-suite optional/skipped coverage is not represented as executed live proof. Independent security/migration rerun above has zero skips.

## Separate transfer-stack restriction

The GO above applies to the **already integrated, tested commit**, not blanket approval for merging old standalone owner PR heads or any alternative sequence.

Pinned cumulative transfer tips: S1 `709c75d7`, S2 `ba7ba2d1`, reliability `93b4e79f`, observability `931c1f20`, hardening `93e4a81b`, onboarding `5ff2254e`, ops `d42cb056`, validation `56a5d1eb` (full SHAs in evidence/pins). S8 and the candidate have identical backend/security/shared/frontend/workflow implementations. Schema progression remains 0.22→0.23→0.23→0.24→0.25→0.26→0.26→0.26.

Literal synthetic sequential composition on current main reaches S6, then conflicts in `SESSION_HANDOFF.md`. An additional isolated simulation that resolves **only** documentary handoff conflicts reaches S8 and then conflicts in both the handoff document and `frontend/tests/e2e/demo-recovery.spec.ts`. This simulation stops without resolving the test or weakening assertions. Both outcomes are retained; the raw branch sequence is not falsely described as entirely conflict-free.

Therefore:

- **Exact integrated commit 36bd05ee: GO for canonical landing**, subject to ordinary required owner/protected-branch approvals.
- **Alternative individual-transfer merge sequence: HOLD at unresolved documentary/test composition** until its final application/test union matches the reviewed candidate and its actual final SHA receives CI. Earlier source PR heads are not separately certified.

The integrated candidate's own conflict resolution is inspected, includes current main and has passing actual same-SHA browser/unit/security evidence. Its technical GO does not require reconstructing the alternative conflicting path.

## Release limits

No merge, deployment, production edit, enforcement change, paid model request or GitHub approval was performed. Customer deployment remains **NOT APPROVED by this review**: staging/provider/operational and release-authority gates are separate. Fresh production changes or a new main that changes the landing union require revalidation; this recommendation is exact-SHA, not permanent branch approval.
