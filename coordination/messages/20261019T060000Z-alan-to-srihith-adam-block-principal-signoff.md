# MSG: `block_principal` added to `shared.rl.DefenseActionName` (verbal sign-off recorded)
- ID: `20261019T060000Z-alan-to-srihith-adam-block-principal-signoff`
- From: Alan
- To: Srihith (owner of `shared.rl.DefenseActionName`), Adam (FYI)
- Kind: `contract-ack`
- Timestamp (UTC): 2026-10-19T06:00:00Z
- Branch / commit / PR or issue link: `feat/alan/shared-block-principal` (PR to follow)
- Related subsystem(s): shared/shared/rl.py, shared/generated, standards rule tables, rl-defense
- In-Reply-To: `20261019T043718Z-alan-to-srihith-adam-block-principal-action`
- Summary (facts, not assumptions):
  - Srihith signed off **verbally**, as Alan reported to the agent that made this change.
    There is no written ack from Srihith in the repo yet.
  - This change does what the proposal called "Later": `"block_principal"` is appended to
    `DefenseActionName` (additive Literal member). The generated JSON Schema/TS contracts
    are regenerated. Both standards rule tables list it as unmapped. D3FEND D3-AL is
    named as the nearest candidate, but no mapping is asserted without human review.
  - Unchanged: DefenseSimEnv (22 actions, 48 features), every simulator checkpoint, and
    `PolicyRunner`'s refusal of live v2 checkpoints. `PlatformFacts` has no principal-block
    state, so the backend recommendation path still cannot serve a v2 policy.
- Breaking change? No for producers. Consumers that switch exhaustively over the action
  name need a new arm. The frontend lab maps (`frontend/lib/lab*.ts`,
  `components/node-graph.tsx`) fall back on unknown actions; simulator bundles never
  contain it.
- Action required by recipient: Srihith, please confirm the sign-off in writing (reply
  here or on the PR) so it is on record.
- Evidence: see the PR's test plan.
