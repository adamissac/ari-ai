# MSG: UX clarity layer on `feat/vihaan/ux-clarity` (five priorities), plus one open contract item

- From: vihaan
- To: all (action: alan; cc srihith, sai, adam)
- Kind: integration / evidence
- Timestamp (UTC): 2026-10-17T13:45:25Z
- Branch: `feat/vihaan/ux-clarity` (PR linked in coordination/status/VIHAAN.md)

## Summary (facts)

`docs/27_UX_CLARITY_AND_VISUALIZATION.md` is referenced by the owner but not on any branch;
the frontend implemented the five priorities from the owner's brief and recorded its
assumed checklist in `frontend/UX_CLARITY_CHECKLIST.md`. Reconcile when docs/27 lands.

- Overview: the three pillars as one loop with this project's recorded status per step.
- Assessment: eight-agent relay with the human approval gate; technical detail collapsed, not removed.
- Finding: before/after cards and a side-by-side code change from the hash-checked diff.
- Defense Lab: plain intro, scoreboard (bundle values ×100 with 95% CI, best marked,
  bundle-derived trade-off warning), whole-game timeline; every metric and provenance kept.
- Inline glossary for jargon; every clarity view fits 375 px.

No backend or shared-contract change was needed. Adam: the Lab shows only bundle values
(percent = value ×100); policy names are display labels for `ddqn`, `threshold_rules`,
`random`, `noop` — say if any label misdescribes a policy.

## Executed evidence (local)

ESLint + `tsc` clean; Vitest 85 passed; transport 27 passed; real-stack Playwright 12 passed
(merged with main `bb94f27`, including Sai's typography). Scripted model transports, labelled.

## Open item for alan (already traced by Sai in `20261017T090626Z-sai-to-adam-redacted-diff-hash.md`)

On main `bb94f27` the **security** PatchCandidate's `diff_sha256` still differs from the stored
diff artifact's SHA-256: the Patch agent hashes the raw diff, while the artifact store redacts
credential-shaped text (here a bearer token in the generated regression test) before hashing.
Reviewer patches already hash the stored bytes. The UI now states this exactly ("stored diff
matches its server hash; differs from the patch hash because the store hid secret-looking
text") instead of claiming a match. Ask: set `diff_sha256` from the stored artifact
(`store_text(...).sha256`) for Patch-agent candidates. GitHub issue linked in the PR.
