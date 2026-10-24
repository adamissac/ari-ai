# Integration workstream — 2026-11-02 release branch status

Branch: `integration/2026-11-02-release` on m-alan08/ari-ai (base: upstream/main @ 64bb24a2).

## Merged workstreams (in dependency order)
- upstream #412 Phase 6.5 @ a9f5ff31 (merge 87ad6266)
- upstream #458 Phase 7C @ db0a631d (merge a682e1a1)
- fork #2 Live Defense E2E @ e187e9a2 (merge e486d03c)
- fork #1 execution reliability @ 17c3ded0 (merge 83781d5b)
- fork #3 investigation observability @ b44b28aa (merge f9ae4933)
- fork #4 security hardening @ 92178d0e (merge b011c878)
- fork #5 deployment/ops @ c7c5336f (merge 2a3e89dc)
- fork #6 customer onboarding @ 8b366fc5 (merge 2292f350)

## Resolutions of record
- Alembic collision: fork #1 kept 0016 (execution_reliability); hardening's
  repo-disconnect renumbered 0016→0017. Head pin in test_parallel_migrations is 0017.
  **release-validation: preflight must expect head 0017.**
- Repository disconnect (hardening × onboarding): union semantics — sets
  `disconnected_at` kill-switch AND clears `installation_id` + `automatic_assessments`
  AND revokes `deploy_commit_mappings`; reconnect endpoint retained (access re-verify
  only when a stale installation link remains). `Repository` contract gained
  `disconnected`/`disconnected_at` fields (SCHEMA_VERSION 0.24.0).
- worker.py: reliability loop kept wholesale + phase7c JobDeferred (jobs.defer) +
  alerts import union. execute_control accepts JobContext.effect guard (F1-adjacent
  but only for adapter calls; provider-request replay F1 remains owned by Grok).
- Codex findings folded in: test_independent_integration.py vendored from
  codex/first-responder-integration-review @ 6e882045; each reproducing defect is
  strict-xfailed with its finding id. Owners: F1/F7/F8 Grok, F2–F5 Devin Reliability,
  F6/F9 Devin Observability, F10 Devin E2E (fixed here).
- F10 fixed: compat test deadline used Python utcnow() vs PostgreSQL transaction
  now(); now sets deadline genuinely in the past.
- F9 fixed at integration level: phase7c schema pin updated to assert the composed
  0.24.0 (all reserved versions claimed). Deeper contract-evolution work stays with
  Devin Observability.
- test_preflight.py restored alembic_version to a hardcoded '0015', polluting the
  shared test DB and breaking later upgrade() calls (surfaced as test_sandbox_target
  failure). Now captures and restores the real head. Flagging for the
  release-validation owner: the test is outside the listed protected files but
  adjacent to your preflight work.

## Open tracked defects (from Codex review, awaiting owner fixes)
F1/F7/F8 (Grok), F2/F3/F4/F5 (Devin Reliability), F6/F9 (Devin Observability).
Each xfail flips to XPASS (a strict failure, forcing an unmark commit) when an
owner fix lands on a recomposed head.
