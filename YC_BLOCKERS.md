# Ari AI release blockers — 2026-10-31

Scope: canonical main `9437e217d65aa1be22fa7b4f54f723200cd428c8` and six pinned PR heads in YC_RELEASE_MATRIX.md.
Rank reflects customer risk, not a speculative likelihood estimate.

1. **P1 — Credential literals remain exposed in redacted diffs on main.** An independent
   synthetic-canary probe retains raw Python strings, triple-quoted values and unquoted
   YAML passwords. `ArtifactStore.put_text(kind=diff)` calls this redactor and marks its
   result redacted. This proves a redaction gap, not an observed real customer breach.
   #694 removes the three canaries using realistic unified diffs; its 33 focused tests
   pass. Owner: #694 author m-alan08 / Devin security workstream; Alan independent recheck.
   Required: integrate #694, preserve sealed verification bytes separately, rerun viewer,
   history/log and tenant regressions on the resolved candidate. Never publish real secrets.
2. **P1 — Current-main release checker accepts absent and skipped checks.** Independent
   mocked GitHub responses produce PASS for zero checks and one skipped check; current
   checker lacks exact-candidate binding. #695's 46 targeted checks pass, including
   missing/skipped/wrong-SHA failures. Owner: #695 author m-alan08 / staging workstream.
   Required: integrate #695, set an explicit required-check policy, certify actual candidate
   SHA and deployed SHA. Admin must confirm/configure protected main checks: protection
   API was 404 and rulesets empty; permission-limited visibility remains possible.
3. **P1 release gate — Required safety fixes conflict and remain unmerged.** Main + #693
   + #694 conflicts in `auto_commits.py`. Main cannot inherit branch-only fixes simply
   because branch CI passes. Owner: #693/#694 authors with Claude integrator, Alan review.
   Required: owner-reviewed resolution retaining effect ownership and disconnect lease;
   obtain immutable six-head union commit, regenerate contracts if needed, run complete
   required CI and combined adversarial tests. No independent combined certification exists.
4. **Blocking evidence gap — No current-candidate staging safety rehearsal.** No authorized
   staging endpoint/credentials or deployed candidate receipt was available in this audit.
   No current backup/restore, live provider assessment, delivery reconciliation, queue
   restart or deployment identity was independently observed remotely. Owner: staging
   operator/Adam and #695 workstream. Required: isolated company-owned staging,
   recommendation-only, first responder OFF, explicit target authorization, exact-SHA
   smoke + useful failure/recovery + backup restore + one bounded real-model assessment;
   retain receipts without credentials. NOT VERIFIED cannot become PASS by citation.

## Nonblocking risks and pending operational work

- #696 frontend CI fails a landing animation; 17 local UX tests and 6 API tests pass.
  Owner: #696 / frontend workstream. Fix or document/review the demonstrated flake and
  rerun CI on the union; do not classify this cosmetic assertion as an authorization bug.
- #723 monitor logic: 8 tests pass, but PR remains open and scheduling/alert delivery
  are unverified. Owner: Adam. Verify the scheduled monitor on the default branch and
  a controlled alert/recovery path before an unattended pilot; no uptime/SLO claim.
- #725 restart/host logic: 26 tests pass, but remain branch-only. Owner: Adam.
  Verify stale-worker fencing, carried budgets and no duplicate side effects on the union.
- Passing focused tests do not prove absence of all secret, race or authorization defects.
  No new exploit claim is made for unexecuted scenarios.
