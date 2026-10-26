# RC5 independent check — N9 closed; tested landing security suite passes

**The checked latest-main production union passes the independent security suite: 194 passed, zero failures, zero skips. No new defect was established.** Actual PR #8 remains **HOLD for merge**, because the production candidate has not incorporated newer upstream Verify fixes and has not run full release CI on the resulting landing SHA. This is not another N9 failure.

No production code, integration branch, enforcement, merge or deployment was changed; no approvals or paid provider requests were submitted.

## Exact commits

- Production candidate: `45c7cd6d1ce166b0d2e1fd0b34bb6dd8987b9008`.
- Observed PR head: `9672cc608a67bc5263d645bdc8135032e74df268`; only an automated coordination report follows the production pin.
- Upstream tested: `59cd0b623e1687a71de4b7653ad8171b0c569344`.
- Final observed main: `edfa9b8bfb54cae54c2281e42d2989f60cf7ef70`. Its sole change after the tested upstream is `coordination/status/ADAM.md`; production code is identical. This drift is recorded rather than silently changing the tested SHA.
- Review-only landing commit: `0aa68ffb046a90bae0ae11c909142e939de842d8`.
- Landing tree: `5b28d0c7fcfe0ce5fb760581dc90ff91a1e4c49a`.

The landing commit is a deterministic local simulation inside the isolated review job, **not** a pushed production/integration commit. It merges the production candidate and tested upstream. Only `docs/planning/SESSION_HANDOFF.md` conflicted; this review-only tree explicitly selects that document from canonical main. No product-code conflict was resolved. The actual integration owner must reconcile the handoff documentation before landing; this documentary choice is not an instruction to discard integration history.

## Known findings

Original **F1–F10 and N1–N9: PASS** on this check's original/retained probes. This includes provider-attempt recovery, emergency capacity, queue/lease/deadline fencing, OFF cancellation, transactional repository disconnect/finalization, target-installation reconnect, tenant boundaries, historical credential scrubbing, migrations/schema ordering, and N7/N8/N9 source/artifact controls. No existing assertion was relaxed to accept a bad security outcome.

N9's actual implementation change restricts the annotation span from `[^=\n]+?` to `[^=\n;#]+?`. The semicolon can no longer be consumed into the next statement. Both the valid non-secret Python byte-equality reproduction and real stored unified-diff reproduction now pass; literal dictionary/typed secrets remain scrubbed (N8), and nonliteral expressions remain intact (N7). No new redaction defect was established in this check.

The old read-limit fixture input was aligned with the already-approved upstream #607 split: `rate_limit_per_minute=3` becomes `rate_limit_read_per_minute=3` for its GET test. All response/count assertions are unchanged. The independent three-GET/429 and two-POST/429 control also passes. This is a documented input-contract adaptation, not weakening a failing assertion.

## Candidate versus latest-main verification

The candidate alone ran **192 passed, 2 failed, zero skipped** in [run 40243684707](https://github.com/m-alan08/ari-ai/actions/runs/40243684707). Both failures are newly merged upstream #629 requirements:

- `test_imported_pytest_hook_code_replacement_is_flagged`: candidate returns no tampering for reassignment of an imported pytest hook's `__code__`.
- `test_rootdir_symlinked_pyproject_checks_resolved_target[pytest-section-edit]`: candidate fails to flag an edit to the symlink-resolved pytest configuration target.

These are **known upstream fixes absent from this older candidate**, not newly discovered findings named N10/N11. The candidate's N9 fix passes. The original source of the two new tests is canonical #629 at the tested upstream SHA; its assertions were not edited.

After including current main's implementation, **both failures disappear**. Final [run 40243984093](https://github.com/m-alan08/ari-ai/actions/runs/40243984093), controller `36893bca`, checked the exact review-only landing commit above: **194 passed, 0 failed, 0 skipped, 0 test errors**, 31.55 seconds, receipt exit code **0**, GitHub job **success**.

This run includes real PostgreSQL migration/queue/API/history/artifact tests and scripted provider fixtures, not live provider or customer-enforcement evidence. Migration upgrade/downgrade, populated recovery and single 0019-head checks pass. Candidate source and independent fixtures are read-only inside restricted Docker containers with no outbound network/provider credentials, bounded resources and disposable PostgreSQL.

## Merge-equivalence and CI

The N9-cascaded stack is pinned in `pin.json` / `evidence/sequential-composition.json`:
S1 `8a945e04`, S2 `93b4fe82`, reliability `b8ccb7a8`, observability `19b97702`, hardening `87fd7149`, onboarding `e6b7a326`, ops `25904496`, validation `c197a7a5` (full SHAs retained).

It composes cleanly on e41c9dc2 and matches the candidate implementation, with documentary/stored-evidence differences. On newer main 59cd0b62 the literal sequence stops at S3 on the handoff-document conflict. Direct candidate/main merge has the same documentary conflict; there is **no production-code conflict**. The reviewed landing's product union preserves #629 and the previously reconciled quota, delivery, retention, authorization, sealed-diff and Verify behavior.

The original candidate has **24 successful checks, one failed paid-audit report and two skipped checks** (Codex audit and optional live provider). Missing OpenAI credentials are not a product vulnerability or a prerequisite for this manual review. Those product checks do not cover a future actual integration commit that incorporates main.

The successful landing job certifies the **selected independent security/migration suite**, not full frontend/Playwright/deployment/production CI on a posted PR head. Do not use it as blanket same-SHA release approval.

## Execution integrity and retained setup failures

All outcomes are retained:

- Initial matrix run 40243684707: candidate results above; landing setup stopped on the explicit documentation conflict before tests.
- Landing-only setup run 40243735657: also stopped at that conflict before tests. The self-contained Git-clone change was a harness adjustment, not a production edit or assertion change.
- Landing run 40243851981: all 194 tests passed but the prior result-directory cleanup error kept the job failed.
- Final run 40243984093: same landing commit/tree, all 194 pass and cleanup succeeds.

The cleanup correction grants removal permission only on disposable container-owned **result directories**, after candidate containers stop, using the same unprivileged UID, no network, no symlink following and only the results mount. It never changes source, assertions or result bytes. No failed candidate assertion was hidden by a passing landing rerun; the two trees and outcomes remain separate.

The one-off workflow is archived after this check, avoiding automatic audit retries on report updates. No API-key activation, Devin resume or paid model request was needed.

## Decision and next step

- **N9 correction: GO.** Original known findings are closed in the checked union.
- **Selected latest-main landing security suite: GO**, exactly as bounded above; no new finding.
- **Actual PR #8 merge: HOLD.** Incorporate current canonical main, reconcile the handoff document, publish the real updated candidate and run all required release CI on its exact SHA. Verify it retains the checked production union; any new production resolution requires fresh review.
- **Customer deployment/enforcement: not approved.** Final staging/provider/operational evidence and release authority remain separate.

No additional novel product-code correction is prescribed by this review. The remaining technical integration action is to include already-merged upstream #629, not redesign the N9 fix or enable paid automated review.
