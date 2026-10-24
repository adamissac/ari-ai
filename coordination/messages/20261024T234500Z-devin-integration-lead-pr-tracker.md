# MSG: Integration lead — live PR disposition tracker (pilot merge lane)

- ID: `20261024T234500Z-devin-integration-lead-pr-tracker`
- From: Devin (integration lead session `aedd769fac50460c914b5139579a16e5`)
- To: all agents landing pilot PRs (incl. session `174c2824231b457a8954115bff931884`, Alan's lane)
- Kind: status / merge-order record
- Timestamp (UTC): 2026-10-24T23:45:00Z

## Merge execution ownership

I am the merge executor for the pilot lane tonight. If you own a branch below,
do not force-push over merge commits; rebase only if asked. Ping me via a
`coordination/messages/` file or PR comment before merging your own PR so we
do not double-merge.

## Dispositions (audited 2026-10-24 against main @ ed5cbf7d)

| PR | Disposition | Notes |
|---|---|---|
| #535 tenant data protection | **CLOSE** — content already on main via merge commit `08114692` | residual diff = docs/status only |
| #551 sandbox-target enum fix | **MERGED** `33d68634` | fixed `AssessmentState.completed` → `COMPLETED`; unblocks every `test` job |
| #531 intel pipeline audit | merge (wave 2) | pilot gate: source redaction |
| #530 release gate + pilot-verify.yml | merge (wave 2) | needed for final verification |
| #527 pilot launch package | merge (wave 1) | includes clean rehearsal test files |
| #548 rehearsal drills | **CLOSE as duplicate** of #527 | same 2 files + lint errors |
| #528 seven-agent live evidence | merge (wave 1) | artifacts + manifest |
| #529 reviewer eval report | merge (wave 1) | docs + scorer fallback tests |
| #549 merge-order coordination | merge (wave 1) | coordination record |
| #533 readiness/heartbeats (0017) | merge (wave 3) | renumber already done; verify down_revision |
| #536 landing rework | merge (wave 4) | frontend only |
| #537 inventory-lite fixture | merge (wave 1) | clean, 8/8 checks |
| #540 GitHub onboarding hardening | merge (wave 3) | overlaps routes/jobs with #530 |
| #496 commit-review navigation | merge (wave 4) | parent of stacked #538 |
| #538 first-user usability | merge AFTER #496 | stacked on commit-review-navigation |
| #532 Defense Lab pilot audit | merge (wave 4) | quarantine fix; recommendation-only |
| #542 intel-store retry fix | merge (wave 2) | verify vs new intel_store on main |
| #543 eval runner retry | merge (wave 2) | single file |
| #550 ledgerlite rehearsal target | merge (wave 4) | new dir |
| #546 get_project authz test + agent defs | merge after CI green | test validates already-correct behavior; gitleaks was stale |
| #545 sandbox role fixture | HOLD — needs rebase | ari-security[bot] (Alan lane); dirty vs main, contract regen |
| #458 Phase 7C live-defense | **HOLD** per Alan 20261024T212131Z + owner instruction | no auto-merge; human/security review |
| #412 Phase 6.5 RL-gated pilot | **HOLD** | conflicts + schema 0.20 vs main 0.21; owner hold |

## Merge order in flight

1. Wave 1: #537 #527 #528 #529 #549 (+close #535, #548)
2. Wave 2: #531 #542 #543
3. Wave 3: #530 #540
4. Wave 4: #533 #532 #536 #496 → #538 #546 #550
5. Held: #545 (rebase), #458, #412 (Alan lane / security review)

## Active regression already fixed

`deploy/sandbox_target.py` used `AssessmentState.completed` (lowercase) — fixed
on main via #551 (`33d68634`). Any branch merged with main after `ed5cbf7d`
carries the fix.

## Alembic chain on main

`0014_automation_opt_in` → `0015_first_responder` → `0016_tenant_rls_intelligence`.
#533 adds `0017_worker_heartbeats` (down_revision 0016) — already renumbered.
