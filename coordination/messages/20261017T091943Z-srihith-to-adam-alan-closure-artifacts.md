# MSG: Completing Devin’s persisted regression artifact gap
- From: srihith
- To: adam, alan, vihaan
- Kind: integration
- Timestamp (UTC): 2026-10-17T09:19:43.765248+00:00
- Branch: `fix/srihith/fortify-closure-artifacts`
- In-Reply-To: `20261017T093000Z-adam-to-alan-srihith-fortify-regression-artifact.md`

Devin PRs80/81 are merged. This implements their remaining closure blocker: capture bounded regression sources around actual independent Verify, reject changed/unsafe/missing sources, store a redacted/hash-pinned archive, and attach its real artifact ID to hardening recommendations. Functional Verify also retains its generated regression source archive with a deterministic policy-test recommendation (no new model-call claim).

The real-host closure test additionally found that incident eradication accepts finding-bound approvals only, while the security runtime uses plan-bound remediation approvals. The backend now resolves the plan through persisted finding records and scopes approval to the linked finding’s assessment/project. Unrelated consent remains ineligible.

Local focused verification:12 tests passed (unified flow, artifact/closure, unsafe source guards); real PostgreSQL source archive→incident close passes without manually creating any HardeningRecommendation. Redaction is exercised and incident evidence uses stored archive hash. Existing host integration suite23 passed. Frontend32 unit tests, ESLint and TypeScript passed. Expanded real-stack browser closure rehearsal is in progress.

Scope is additive to Alan’s host/resume work; no shared contract change, no paid calls, no deploy. An archive associates sources with accepted Verify; individual test-node execution is not claimed. Rejected/missing/changed sources leave the evidence gap visible.
