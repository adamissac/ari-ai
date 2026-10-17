# Product readiness audit: October 17, 2026

Tracking issue: [#244](https://github.com/adamissac/ari-ai/issues/244). This document is the dated audit snapshot; subsequent execution updates belong on the issue or in evidence-linked follow-up messages.

## Purpose and scope

Srihith's owner-requested comparison of the original project blueprint against implemented code, executed evidence and hosted behavior. This is a team-visible readiness note and prioritized follow-up list, not a claim that the full product is production-ready.

- Primary code/test snapshot: `882daa2e2f7a2b26a1da4b9cdce9fcad17a59c08` (October 17, 2026).
- Publication base: `b44d3726f3471489e4a884c33eb94a7fd71e1bb0`, including the now-green frontend contrast fix #241.
- Newer reported M3 evidence: open PR #243 (approved; CI green at review), head `08ffd64099247eccf0668f084d989bc8c7ad8390`. Its live-result account is attributed below; the original live artifact was unavailable for independent inspection. Onboarding #239 merged after this audit's primary snapshot.
- No product code was changed by this audit. The accompanying branch is documentation/coordination only. Status is a dated snapshot; later work should add evidence-linked updates.

**Assessment:** Ari has a substantial connected prototype with real persistence, tools, executed tests, approvals and verification. The largest unfinished step is a reliable, isolated, end-to-end live-provider journey on an authorized customer repository through the hosted product.

## Feature inventory against the original blueprint

| Feature | Implemented and supported by evidence | Remaining work or boundary |
| --- | --- | --- |
| Codebase understanding | Python indexing; symbols, imports, calls, declared routes; citations pinned to a full Git SHA | JS/TS and more frameworks; dynamic behavior; large-repository performance. Declared routes are not proof of runtime reachability. |
| Intended functionality | Source-cited expectations from docs/tests, uncertainty, authenticated human confirmation/conflict/rejection and revision history | Broader extraction/accuracy evaluation. Inferred intent is not automatically a confirmed requirement. |
| Functional review and repair | Bounded reviewer tool loops, generated behavioral tests, approval-gated candidate repairs, trusted test replay; limited live reviewer runs recorded | Reliable outcomes across unfamiliar apps; broader performance/concurrency/architecture evaluation. Fixture success does not establish general coverage. |
| Seven specialized security agents | Distinct Scout, Probe, Trace, Diagnose, Patch, Fortify and Verify runners, prompts, tools, budgets and typed handoffs; deterministic orchestration | Strict successful live execution through all seven roles remains unproven. See updated M3 account below. |
| Independent verification | Separate Verify runs, fresh environments, actual security/functional results, tamper/scope checks and regression artifacts | Wider check coverage and complete hosted live-model proof. Security-patch-generated tests are not automatically tested on the unpatched version; functional generated tests are. |
| Shared version-aware memory | Persistent code context, expectations, findings and exact-base-SHA candidate regression evidence reused across components | Incremental parser caching/partitioning; measure whether retained evidence improves future assessments. A verified candidate is not proof the patch was merged. |
| Backend control plane | FastAPI, PostgreSQL/migrations, durable queue, leases/retries, SSE replay, scopes, two-person approvals, CSRF/authz and hash-chained audit | Hosted operational validation, worker uptime/recovery and production hardening. Passing DB/queue readiness alone is insufficient for a live assessment. |
| GitHub integration | Backend user-access checks, installation-token support and exact-commit fetching; org → repo → commits onboarding merged in #239 | Hosted App/OAuth/webhook setup and end-to-end validation against Railway/Vercel credentials. |
| Code-change monitoring | Signed push/PR normalization, delivery deduplication, impact correlation and reassessment policy; scripted M7 API chain executes real components | Actual hosted webhook delivery and sustained worker-operation evidence. No demonstrated 24/7 customer operation. |
| Runtime monitoring | Token-authenticated aggregate route signals, anomaly scoring, correlation, feed and RL inputs | Allowed sources are runtime_demo/replay/simulated. Production telemetry, cloud/auth/log connectors and dependency-advisory polling remain. An anomaly is not a confirmed attack. |
| RL defense | Genuine Gymnasium simulation, Double DQN training/checkpoints, baselines, held-out evaluation, explanations and typed recommendations | Real-world transfer/calibration, more representative topologies and fewer unnecessary disruptive actions. Recommendations never execute real infrastructure actions. |
| Product UI | Backend-connected projects, findings, approvals, timelines, diffs, expectations, incidents and Defense Lab; real-stack browser tests use scripted model turns | Hosted live-provider browser journey and complete customer onboarding. Public /projects redirected to the labelled simulated demo when checked. |
| Standards and incident handling | Validated CWE/ATT&CK/D3FEND identifiers, deterministic CVSS calculators, SARIF, NIST-aligned incident records with evidence/approval gates | Broader reviewed mappings; reconcile CVSS documentation; partial OWASP LLM self-controls and no customer-app LLM-risk check templates. Not certification. |
| Commercial product | Proposed pricing page and presentation | Purchase/checkout, subscriptions, usage metering and enforcement of repo/codebase/assessment limits; paid-pilot validation. |

Implementation sources: [code intelligence](https://github.com/adamissac/ari-ai/tree/882daa2/code-intelligence), [reviewer](https://github.com/adamissac/ari-ai/tree/882daa2/code-review), [security agents](https://github.com/adamissac/ari-ai/tree/882daa2/security-agents), [backend](https://github.com/adamissac/ari-ai/tree/882daa2/backend), [frontend](https://github.com/adamissac/ari-ai/tree/882daa2/frontend).

## Important findings

### Hosted product is reachable, but live integrations are unavailable

Read-only checks on October 17 returned:

- https://ari-ai-lake.vercel.app → HTTP 200.
- https://ari-ai-lake.vercel.app/projects → redirected to `/demo`.
- https://ari-ai-production-76d4.up.railway.app/healthz → HTTP 200, status `ok`.
- https://ari-ai-production-76d4.up.railway.app/readyz → HTTP 200, database and queue true, **`llm_mode: unavailable`, `github_app_configured: false`, `webhook_secret_configured: false`**.

The readiness route deliberately bases HTTP success on DB/queue reachability; it does not prove the worker, App, webhook or live-model path works. Configure authorized credentials in the hosting secret store, not in GitHub issues, source files or chat. The presentation site is a separate deployment and is not product-operation evidence.

### M3 live evidence: retain both the older failure and the newer reported result

The committed [13:57 UTC record](https://github.com/adamissac/ari-ai/blob/882daa2/coordination/messages/20261017T135740Z-srihith-to-alan-live-seven-role-result.md) shows Scout/Probe live, then Probe inconclusive and no later role execution. Parameter-discovery fixes subsequently landed.

**Newer update, reported in #243:** a later live attempt reached all seven roles, with **six successful and Fortify `SCHEMA_INVALID`**. The old live test nevertheless passed. The exact original report is unavailable to the PR author and this auditor, so its precise Fortify cause is not established. The PR reproduces a plausible invalid-CWE/D3FEND submission sequence with scripted turns, improves prompt/schema repair and report retention, and makes failed Fortify fail the M3 assertion. This is pending review, not a verified complete live run.

Acceptance must require every required role to succeed in live mode, valid handoffs, actual execution/verification evidence and retained inspectable artifacts. Do not call an assessment's terminal `completed` state or a weak green test proof that all seven agents succeeded.

### Security coverage and sandbox boundaries

- The check library principally implements ownership/access control and input bounds. Human review markers still include `security-owner:pending-human-signoff`; record actual reviewer approval and renderer hashes.
- Docker isolation has real-container CI evidence. The new Vercel driver tests use a fake microVM, not demonstrated live microVM execution.
- `code_review.shared_sandbox.build_sandbox()` still defaults to local-process execution unless configured; the security driver separately defaults to Docker. Verify a consistent isolated production path for both pillars and fail closed on unsafe configuration.
- Verify reruns the original Probe check and new Patch tests on the patched workspace. A security patch's new regression tests failing on the original workspace is not automatically established today; #243 identifies this gap explicitly.

Sources: [sandbox selection](https://github.com/adamissac/ari-ai/blob/882daa2/code-review/code_review/shared_sandbox.py), [Vercel driver tests](https://github.com/adamissac/ari-ai/blob/882daa2/security-agents/tests/test_vercel_sandbox.py), [check review packet](https://github.com/adamissac/ari-ai/blob/882daa2/docs/security/CHECK_TEMPLATE_REVIEW.md).

### RL is implemented, with a material simulation tradeoff

Independent recomputation of the stored protocol-v1 DDQN episodes: **5 training seeds, 1,500 episodes; mean return -29.09974, compromise 7.133%, false disruption 75.039%, uptime 94.434%**. This matches the committed rounded results. False disruption concerns disruptive actions on nodes not yet compromised, not the percentage of all incidents falsely detected. The five-node mapping is hand-configured, and these results do not establish real-world effectiveness.

Sources: [comparison](https://github.com/adamissac/ari-ai/blob/882daa2/rl-defense/results/protocol-v1/COMPARISON.md), [raw episodes](https://github.com/adamissac/ari-ai/blob/882daa2/rl-defense/results/protocol-v1/eval_episodes.jsonl.gz).

### Standards implementation is partial and some documentation is stale

- The [OWASP LLM coverage matrix](https://github.com/adamissac/ari-ai/blob/882daa2/docs/security/OWASP_LLM_TOP10_COVERAGE.md) records partial platform controls and gaps; every customer-application assessment column is `unsupported`.
- Runtime Trace currently imports CVSS v3.1 for the platform severity level; v4.0 is available separately/provisionally. Some READMEs still say v4.0 is canonical runtime severity. Reconcile code, API/UI wording and docs before external claims.
- ATT&CK/D3FEND mappings classify supported evidence/recommendations; they do not establish that every technique is detected or every defense implemented.
- NIST incident handling records human decisions and evidence; it does not execute real containment/recovery actions or establish compliance.

### Pricing, capacity and product validation remain unfinished

The product `/pricing` source still proposes **$40/seat**, while the owner-approved presentation proposes **$99/$299/$799 plus negotiated Enterprise**, all features included, differentiated by repos/codebase/assessment usage. Align both surfaces before presenting one commercial model. None is evidence of working billing or validated willingness to pay.

The presentation's 100K/500K/2M source-line limits are proposed packaging, not measured capacity. Current ingestion defaults cap total bytes at 32MB and 10,000 files, and large indexes load as one payload. Multi-repository findings also lack a repo id, so UI links are withheld for multi-repo scopes. Benchmark representative repositories and costs before committing to plan guarantees.

## Prioritized follow-up checklist

Owner lanes below are routing suggestions from `coordination/OWNERSHIP.md`, not new assignments or authorization to spend on live runs. Reuse existing tasks/PRs; do not create competing implementations.

- [ ] **P0: finish strict live M3 proof.** Alan/Sai/Srihith: review #243, retain full artifacts, require seven successful live roles, inspect patch + independent Verify, and only rerun paid tests with owner-authorized budget. Also establish before/after behavior of newly generated security regression tests.
- [ ] **P0: complete hosted integration setup.** Adam/Srihith/Vihaan: coordinate #239, App/OAuth/webhook/LLM configuration, real authorized sign-in → repo → exact commit → assessment → approval → Verify browser journey. Demonstrate a real signed hosted push and persistent evidence; no demo data in the live console.
- [ ] **P0: validate isolation across the whole workflow.** Alan/Sai/Srihith: real hosted sandbox evidence for review and security; no customer tests on the API/worker host; deny unsafe fallback; confirm scope, network, timeout and cleanup boundaries; finish human template sign-off.
- [ ] **P1: broaden detection and evaluation.** Alan/Sai/Sarosh: more reviewed check classes, independent clean/vulnerable/bad-patch repositories, precision/recall and false-positive reports. Do not generalize from payments-lite alone.
- [ ] **P1: prove scale and language coverage.** Sarosh/Srihith/Vihaan: JS/TS extraction, incremental/partitioned indexing, multi-repo finding attribution and measured runtime/memory/cost against proposed plan sizes.
- [ ] **P1: finish real monitoring and operational proof.** Srihith/Adam: production telemetry connectors, calibrated signals, advisory ingestion, worker restart/delivery recovery and sustained-operation evidence. Keep anomaly/confirmed-incident distinctions.
- [ ] **P1: align standards and documentation.** Alan/Srihith plus consumers: consistent CVSS semantics, reviewed mappings, explicit OWASP gaps, and updated milestone/README status tied to evidence. Frontend contrast issue #240 is resolved by merged #241 and its green CI; do not reopen it as an outstanding blocker.
- [ ] **P1: align and implement commercial packaging.** Product owner/Srihith/Vihaan: reconcile product and deck pricing; define maintained-source counts, meter usage, enforce approved budgets and implement subscriptions/checkout when ready. Measure delivery cost and support time.
- [ ] **P2: improve RL transfer and disruption tradeoffs.** Adam: reduce false disruption while tracking compromise/critical-asset loss/uptime, expand topologies and noisy scenarios, retain held-out protocols. Keep recommendations simulation-derived until validated.
- [ ] **P2: validate customer value.** Product owner/team: observed design-partner sessions, task completion, accepted fixes, time-to-verification, support burden and willingness to pay. No fabricated interviews, savings or production results.

## Verification performed for this audit

Fresh isolated snapshot, Python 3.12, frozen dependencies, no live model calls or customer-target execution:

```sh
RUN_LIVE_LLM_EVAL=0 RUN_DOCKER_SANDBOX=0 uv run --frozen --python 3.12 pytest -q \
  shared/tests monitoring/tests backend/tests code-review/tests standards/tests \
  tests/security code-intelligence/tests security-agents/tests
```

Initial result: **1,035 passed, 35 skipped, 1 failed in 265.65s**. The failure was `test_actual_payments_target_and_canonical_consumer_fixture`: the initial isolated Git archive lacked `.git`, so `git rev-parse HEAD` failed. After restoring metadata for the exact audited commit, the two owned-target tests passed (**2 passed in 0.49s**). This resolves that audit-environment failure; the complete suite was not rerun, and no application source was changed.

Additional verification:

- `python -m standards.owasp_llm --check`: **0 matrix problems** (structural consistency, not comprehensive risk coverage).
- Recomputed the stored RL evaluation metrics directly from raw episode records; no fresh retraining claimed.
- Checked public product redirects and backend health/readiness, read-only.
- Inspected CI and PRs. Latest frontend fix #241 merged as `b44d372`; [frontend CI succeeded](https://github.com/adamissac/ari-ai/actions/runs/39066410222). Existing security-agent [CI at the audited commit](https://github.com/adamissac/ari-ai/actions/runs/39065747476) passed, including its Docker job.
- Live-provider/Docker opt-in tests were skipped locally; no fresh browser E2E, paid LLM call, production attack, actual checkout/payment or production-security certification was performed.

## Team action

Please use this issue as the shared readiness checklist. Reply with task/PR links and exact evidence (commit, command, environment/provider mode, results, retained artifacts and limitations). Update a checkbox only after its acceptance evidence exists. Do not mark a feature complete based solely on documentation, simulated UI, model prose, a terminal assessment state or a skipped test.
