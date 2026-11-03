# Ari AI independent release matrix — 2026-10-31

Canonical repository: `adamissac/ari-ai`. Deadline: November 2, 2026.
Main inspected: `9437e217d65aa1be22fa7b4f54f723200cd428c8`. This is a snapshot audit, not approval of a deployment.

| PR | Head SHA | Risk | Known finding | Fix status | Tests | Verdict |
|---|---|---|---|---|---|---|
| [#693](https://github.com/adamissac/ari-ai/pull/693) | `c3d5e552e4fe8e9b66dbf30fab190609e42ec5c9` | High | Ambiguous review writes, ordering and duplicate ownership | OPEN, unmerged; focused checks pass; combined tree unverified | 37 passed on current main plus exact PR head; positive/negative marker and worker ownership tests | HOLD |
| [#694](https://github.com/adamissac/ari-ai/pull/694) | `72753087abef39a84103fe9fbcf43248430a7ebb` | Critical | Disconnect/write-token ordering; literal secrets in viewer diffs | OPEN, unmerged; focused checks pass; combined tree unverified | 33 passed on exact head; includes concurrent disconnect and artifact redaction | HOLD |
| [#695](https://github.com/adamissac/ari-ai/pull/695) | `9cbacc3ed5a787992e8e4de95021faa2ba31abcd` | High | Missing/skipped checks and wrong-SHA certification | OPEN, unmerged; focused checks pass; combined tree unverified | 46 passed on exact head; staging/preflight/migration/signoff regressions | HOLD |
| [#696](https://github.com/adamissac/ari-ai/pull/696) | `e0622b8d91dfb332cea5587147eda3418f3cd810` | Medium | Authorization confused with effective delivery settings | OPEN, unmerged; focused checks pass; combined tree unverified | 6 API + 17 frontend unit tests passed on exact head; remote e2e failed on landing animation | HOLD |
| [#723](https://github.com/adamissac/ari-ai/pull/723) | `56204e4aa073540125489ac7e54a080ec6abea3d` | High operational | Outage monitoring after October 28–30 outage | OPEN, unmerged; focused checks pass; combined tree unverified | 8 monitor unit tests passed; scheduled monitor not verified deployed | HOLD |
| [#725](https://github.com/adamissac/ari-ai/pull/725) | `79067534d044c097140b5aa60469caeb1629cb33` | High | Worker state loss and unhelpful failed assessments | OPEN, unmerged; focused checks pass; combined tree unverified | 26 restart/host tests passed on exact head; fake orchestrators | HOLD |

## Exact composition

All six heads merge individually into this main in `git merge-tree --write-tree` (exit 0).
Sequential local composition main → #693 succeeds at local commit
`7e5c7351598255e5394df45b5ca4a5a1a00e36a0`, tree
`d81fd73128aaab1e7b2604efd307984974114d09`. The 37 pipeline tests ran on that commit.
Adding #694 fails (exit 1) in `backend/backend/auto_commits.py`, `backend/README.md`,
and `CHANGELOG.md`. The source conflict combines delivery idempotency and disconnect
protection; selecting either side wholesale is not a verified resolution.
#694/#695 and #695/#696 also have documentation conflicts. #693/#725 conflicts in
CHANGELOG. These are observed comparisons, not an exhaustive pairwise proof.
**No complete resulting integration commit exists in this audit.** Git conflict-tree
object IDs are diagnostic only and must never be presented as a tested candidate.

## Current main and CI

103 selected main tests passed: tenant isolation, project authorization, job queue,
operator budgets, delivery, migration round-trip, and security regressions.
GitHub reports successful backend, frontend e2e/unit, security/container, review,
intelligence, secret scanning and other jobs for the exact main SHA (raw check-run
records retained). This does not invalidate the independently reproduced gaps.
All six PRs remain open; #696 e2e failed. Its failure is
`landing.spec.ts:226`, missing `data-active=true` while scrolling; the first-customer
journey passed in the same run. Treat as a nonsecurity CI/demo concern until reproduced.
All six have skipped candidate `pin`, `strict-regressions`, `independent-codex`,
`publish`, and CodeRabbit checks. `live` is skipped where present. #723 scheduled
uptime/storage checks are skipped on its PR event; its monitor unit job is green.
Skipped release-only jobs are not automatically defects, but provide no certification.
Main protection endpoint returned 404; repository rulesets returned an empty array.
Active server-enforced required checks were not established; admin must confirm/configure.

## Concurrent work and prior reports

Captured open/recently merged PR metadata and issue #559 discussion. Recent main merges
#736 and #717 are status documentation; #679 adds repository controls, #683 makes
no-HTTP-entrypoint repositories reach functional review, and #681 adds JS/TS text indexing.
Claude/Devin coordination reports October 27 live JS assessments on `139ce727`, with
findings remaining hypotheses and security agents skipped. Those are historical author
reports, not independently rerun staging evidence for this candidate. No assertion is
made that either agent has finished unpublished work. Older release reports, including
`b6d5108b-independent`, bind different SHAs and cannot certify this release.
#695's own staging report still lists deployed staging, remote strict smoke,
backup/restore and real-model authorized assessment as missing; its local rehearsal
on an older SHA is not reused as current evidence.

## Evidence and reproducibility

See [evidence manifest](docs/reviews/2026-10-31-independent-release/MANIFEST.md).
All locally executed tests use Python 3.12 from the existing workspace venv, explicit
PYTHONPATH to the isolated checkout, disposable PostgreSQL, synthetic credentials and
fake providers. Frontend focused tests use existing Vitest 5.0.5 dependencies.
No production tests, customer scans, paid model calls, deployment or canonical merge
were performed. Local merge commit #693 is an audit-only composition.
