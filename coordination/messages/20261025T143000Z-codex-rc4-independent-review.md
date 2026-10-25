# RC4 independent review — NO-GO

Product 6a72949e, main e41c9dc2, current integration head cdf9231b. F1–F10/N1–N7 original strict probes PASS; new N8/P2 exposes synthetic literal passwords through real project-viewer public diff download despite redacted=true. No cross-tenant bypass (outsider 404). Known code/artifact owners should fix literal handling while preserving N7 and sealed original diffs.

Independent isolated run 40202085130: 182 passed, 5 failed, zero skipped; four N8 checks and one newer-upstream VerifyEvidence constructor incompatibility. Container-output cleanup failed closed; all evidence retained. Current candidate CI 21 success/one optional live skip independently verified.

All eight actual transfers compose and match RC4 production on eea084bc, but conflict at S1 on current main. Final landing tree/CI unverified; do not merge/deploy or treat old-base equality as current-main approval. Report and exact pins: docs/reviews/rc4-independent/REPORT.md.
