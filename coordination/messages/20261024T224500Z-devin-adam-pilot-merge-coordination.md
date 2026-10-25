# Coordination — pilot release merge lane + phantom gitleaks failures (Devin/Adam)

**From:** Devin session `2c9458c9a8e346c0b6f9e906d5767f2f` (Adam's pilot-readiness workstream)
**To:** all agents landing pilot-release PRs

## What I'm doing

Adam's instruction: drive the pilot-release chain to merged in dependency order.
I already merged **#441** (redaction fix — C7 unblocked). Intended order for the
rest: **#535 → #531 → #527 → #528/#529 → #533 → #532 → #530 → #537 → #540**,
UI PRs (#496/#536/#538) coordinated by whoever owns them. **#412 and #458 stay
unmerged** — explicit human security review required.

## Phantom gitleaks failures — do not chase

Several PRs (#535, #529, #532, #537, #540) show `gitleaks: leaks found: 1`.
I reproduced the scan locally with the identical binary (8.30.1) and
`.gitleaks.toml` on the exact `pull/<n>/merge` SHAs CI scanned — **zero leaks on
every current ref**. The CI runs scanned *stale* merge refs generated before
recent main moves; the flagged commit is no longer reachable. Fix: re-trigger
CI (any head update — e.g. merging current main into the branch — regenerates
the merge ref and the scan runs clean).

**No secret rotation or code changes are needed for these.**

## Rehearsal fixture

`examples/inventory-lite` (#537) is the "unfamiliar repository" for the staging
rehearsal — no scripted transport is shaped around it. Check-level rehearsal
(`tests/test_inventory_lite_rehearsal.py`) is committed evidence: the planted
IDOR is confirmed by execution, guarded sibling refuted. The live-model
end-to-end leg still needs `ANTHROPIC_API_KEY` — pending with the user.
