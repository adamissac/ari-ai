# MSG: Srihith has left the project; interim approval for `shared/`
- ID: `20261019T070000Z-alan-to-all-srihith-handover`
- From: Alan
- To: all (Adam, Sarosh, Sai, Vihaan)
- Kind: `decision`
- Timestamp (UTC): 2026-10-19T07:00:00Z
- Branch / commit / PR or issue link: `feat/alan/srihith-handover`
- Related subsystem(s): shared/, backend/, monitoring/, coordination
- Summary (facts, not assumptions):
  - Srihith is no longer working on the project (stated by Alan, 2026-10-19).
  - Interim, until the team decides otherwise: Alan approves `shared/` contract changes.
    Affected consumer owners still review, per coordination/CONTRACTS.md.
  - `backend/` and `monitoring/` have no named owner. Until one is agreed, changes there
    go through a PR reviewed by any remaining owner, with CI green.
  - `block_principal` in `shared.rl.DefenseActionName` (PR #324, merged 854944f) rests on
    Srihith's verbal sign-off, as Alan reported it. The written confirmation requested in
    `20261019T060000Z-alan-to-srihith-adam-block-principal-signoff` can no longer be
    obtained. Alan, as interim approver, stands behind the change.
- Interface requested/proposed: none.
- Breaking change? No.
- Action required by recipient: say if you want to take over `backend/`, `monitoring/`
  or `shared/` permanently; otherwise the interim arrangement stands.
- Evidence: coordination/OWNERSHIP.md, coordination/CONTRACTS.md (this branch).
