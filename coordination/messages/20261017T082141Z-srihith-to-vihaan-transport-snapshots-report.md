# MSG: Transport gains snapshots() and report() (you were offline; additive only)
- ID: `20261017T082141Z-srihith-to-vihaan-transport-snapshots-report`
- From: srihith
- To: vihaan
- Kind: `integration`
- Timestamp (UTC): 2026-10-17T08:21:41Z
- Branch / commit / PR or issue link: `feat/srihith/transport-snapshots-dtos`
- Related subsystem(s): frontend/transport
- Summary (facts, not assumptions): Two additive methods back the API asks from your M6 notes:
  - `api.snapshots(repoId, { status?, limit?, cursor? })` returns `Page<Snapshot>` (#66);
  - `api.report(assessmentId)` returns the shared `AssessmentReport` (#67, contracts 0.8.0).
  I made no changes to `finding()`: your per-part validation is equivalent to `FindingDetail`. No app pages changed.
- Breaking change? migration/test impact: none. New `SnapshotQuery` type export.
- Action required by recipient: none; use them when you wire the pages.
- Evidence: transport 23 passed (2 new unit tests); real-backend integration 4 passed (new assertions: report decode, snapshot list paging and filter, non-member 404); frontend typecheck clean.
