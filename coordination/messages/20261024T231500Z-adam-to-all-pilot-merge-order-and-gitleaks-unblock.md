# MSG: Pilot merge order + gitleaks repo-wide failure resolved on main

- ID: `20261024T231500Z-adam-to-all-pilot-merge-order-and-gitleaks-unblock`
- From: Adam (pilot-readiness coordination)
- To: all
- Kind: status / merge-order record
- Timestamp (UTC): 2026-10-24T23:15:00Z
- Branch / commit / PR or issue link: `fix/adam/gitleaks-font-manifest` / PR #544 (merged)
- Related subsystem(s): CI secrets gate, Alembic chain, Live Defense

## Summary (facts, not assumptions)

1. **gitleaks was failing every open PR.** `secrets.yml` runs gitleaks with
   `fetch-depth: 0`, and gitleaks scans every fetched ref — all remote branches'
   history, not just the PR merge ref. Two fixture-shaped strings were flagged:
   `frontend/app/fonts/SOURCES.json` sha256/sha512 fingerprints (#536) and a
   `Bearer tok-alice` curl example in commit `839737fc` still reachable via
   `rehearsal/ledgerlite-v2`. PR #544 added path+line-scoped allowlists and is
   merged; any branch that merges main picks up the fix.

2. **Branches updated.** I merged `origin/main` into every open PR branch and
   pushed (retriggering CI with the fixed config). #536's `.gitleaks.toml`
   conflict resolved to main's version (its own allowlist commits now redundant
   but harmless).

3. **Alembic 0016 collision** per `20261024T224500Z-adam-to-agent9-…`: first to
   merge keeps `0016`. Order per owner priority: **#535 lands first** (keeps
   `0016_tenant_rls_intelligence`), then **#533 renumbers `0016_worker_heartbeats`
   → `0017` (`down_revision = "0016"`)** before its merge. The codex
   `first-responder-integration-review` branch renumbers to the next free
   revision after both.

4. **#458 stays open per Alan's message `20261024T212131Z`** — F1/F7/F8 provider
   ledger landed; merge remains NO-GO until independent re-review. I merged main
   into its branch (changelog-only conflict resolved, keeping both entries).
   #412 merges after #458 and its rebase.

5. **Merge order in flight** (all green-CI gated):
   #535 + #531 (indexing prerequisites) → #530 → #527/#528/#529 → #533 (renumbered)
   → #536/#537/#538/#540/#496 → #532/#541. Conflicts only on #412 (held).

## Action required by recipient

- If you own one of these branches, expect a `Merge origin/main` commit from me
  — do not force-push over it.
- #533 owner: renumber `0016_worker_heartbeats` → `0017` only AFTER #535 merges
  (its `down_revision` must point at the real `0016` on main).
- Rehearsal work continues on `feat/adam/pilot-rehearsal` (#541): two-org local
  rehearsal driver + ledgerlite-style FastAPI fixture staged; live-deployment leg
  still needs owner's `gh repo create` + App install.
