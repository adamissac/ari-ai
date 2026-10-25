# Independent release re-review: NO-GO

From: Alan / independent review
To: integration, reliability, first-responder, hardening, onboarding and infra owners
Source release: dd530ae3b00d31ecc54a6fb5908a50b8b6b1965d (fork PR #8)
Upstream: dc9a623aca21678bd34a84d61a4bb8433445a59f

Original strict regressions pass with real fixes, but signoff is withheld. Report: `docs/reviews/first-responder-release-rereview/REPORT.md`; strict reproductions and sanitized evidence are committed beside it/on this audit branch. No merge/deploy performed.

Required actions, in dependency order:
1. Infra/reliability: reconcile reused migration identities with latest-main RLS and heartbeats. Both 0017 chains report current while representing different schemas; latest-main-to-release misses job columns, reverse direction omits RLS. File renaming alone is insufficient.
2. First-responder/hardening: disconnect a repo during a provider turn currently permits three additional turns. Cancel active/waiting steps and gate every next turn/tool/final persist on trusted revocation.
3. Onboarding/hardening: fresh installation-check failure must not permit reconnect from cached access; repository picker must not disclose another tenant's connected ID.
4. First-responder/reliability: persist recovery state before send, not only in an exception handler. Abrupt process exit leaves queued work with an unresolved durable ledger; ledger prevents replay but operator recovery is missing.
5. Preserve integration-only F7 enqueue deadlines when taking refreshed #458/#2. Standalone #2 still fails its xfailed assertion when run with --runxfail.

Report contains conditional sequential integration order. These are review findings, not implementation permission or security approval. Do not claim local readiness PASS as customer security signoff.
