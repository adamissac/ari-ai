# MSG: Canonical standards integration, incident persistence and 2026 coverage
- ID: `20261017T041522Z-srihith-to-all-standards-integration`
- From: srihith
- To: alan, sarosh, sai, adam, vihaan
- Kind: contract-ack / integration
- Timestamp (UTC): 2026-10-17T04:15:22.509804+00:00
- Branch: `feat/srihith/standards-alignment`; builds on Alan PR #49 @ `8be2cbc` (merged into branch history).
- In-Reply-To: `20261017T040516Z-alan-to-srihith-standards-contracts-and-incidents-api.md`

Accepting the canonical 0.7.0 standards/incident contracts as the integration basis. 0.6 remains reserved for intelligence memory. This is a proposal on the integration branch, not in force on main until reviewed/merged. Shared validators additionally enforce catalog metadata and deterministic CVSS. Additive fields: SeverityAssessment.cvss, PathStep.attack, HardeningRecommendation.d3fend, DefenseRecommendation.d3fend, IncidentDetail envelope. Generated schemas and fixtures regenerated.

Backend now persists incident documents (migration0005), authenticates/actions owner role + CSRF, audits/replays timelines, and resolves project links, actual independent Verify and regression artifacts before pure incident rules. Runtime correlation only reports events; human triage declares an incident. Host.record_standards updates classifications atomically. Report includes persisted Finding.standards + hardening records. No infrastructure actions are executed.

Producer integration reuses standards.mapping and cvss_assess. No automatic CWE-CAPEC-ATT&CK equivalence. Explicit complete CVSS metrics cite executed evidence; absent metrics stay unscored. RL mappings remain proposed/simulation-derived. Frontend transport adds typed incident endpoints and display helpers, not mounted pages. Vihaan retains page integration.

OWASP2026 published official release verified. Both2025/2026 catalogs and coverage matrices pinned, with stable year-qualified IDs and honest partial/gap labels. Coverage is platform self-assessment; no customer-app scanning claim.

Executed locally: root suite193 passed/2 opt-in live skips (TSC+RL installed); security/reviewer suite400 passed/11 optional skips; RL82 passed; frontend transport16 unit tests and real HTTP/PostgreSQL4 tests; standards16 tests including3047 FIRST JS oracle vectors; root/standards/incident mypy and Ruff, generated freshness, links233 checked/0 issues. Existing isolated security provider SDK fallback type annotation issue is outside this change. No paid live calls or deployment.

Review the integration PR before adopting these additions. Backend consumers should use IncidentDetail{incident,standards} and POST /incidents/{id}/actions. Rebase other standards producer changes on these canonical helpers to avoid duplication. Rendered frontend standards/incident pages and a paid live-model rerun remain separate gates.
