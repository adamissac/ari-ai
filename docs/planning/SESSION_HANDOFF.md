# Session handoff log

Append-only. Newest entry at the top. Every development session (human or agent)
adds an entry before ending.

## Template

```
### YYYY-MM-DD — <who / agent> — <task IDs>
- Did:
- State of the code (what exists now, verified how):
- Commands run and results:
- Decisions made (ADR links):
- Assumptions / open questions (RQ links):
- Next steps:
- Warnings for the next session:
```

---

### 2026-10-17 - Alan (Claude) - P1 SARIF and OWASP LLM agent evidence
- **Did:** #108 (shared 0.10.0 `cvss_v31`, worker `host.record_roe`) was merged by Adam at an older head. #112 reverted the Trace data-sensitivity fallback (main had been fixed by #107 instead). #109 updated the SEC task board. #114: SARIF 2.1.0 export validated against the pinned OASIS schema. #116: OWASP LLM 2026 matrix rows gain security-agents controls and root tests.
- **State of the code:** all offline or replay. M3 is still not met (no live seven-role run). NIST SP 800-61 alignment was already on main.
- **Commands run:** security-agents 452 passed, 12 skipped. standards 190 passed. tests/security plus standards 203 passed. Report 225 passed. Smoke writes `findings.sarif.json`.
- **Decisions:** severity to SARIF level is a project mapping. P1 started before the M3 live run because only a key holder can complete it and the user granted full control.
- **Next steps:** a key holder runs `RUN_LIVE_LLM_EVAL=1 LIVE_SEVEN_MAX_USD=8 .venv/bin/python -m pytest -q -m live tests/test_live_provider.py -s` in security-agents. Srihith: backend `record_roe` persistence and the RoE endpoint.
- **Warnings:** merge only after `gh pr checks` shows every job complete on the PR's current head (GitHub's PR head can lag a push).

### 2026-10-17 — Adam — project journey
- Did: Project page shows Understand, Review, Security test, Repair, Verify, and Monitor from the latest assessment's event log and the finding list. A phase the log did not enter stays skipped or not started. Verification is completed only when a loaded finding is verified or hardened.
- State of the code: branch `feat/adam/project-journey`. Frontend unit tests, typecheck, and lint passed locally (34 unit tests). Browser e2e was not run.
- Commands run and results: `npm test -- --run tests/unit/lib.test.ts` 34 passed; `npm run typecheck` clean; `npm run lint` clean.
- Decisions made (ADR links): none.
- Assumptions / open questions (RQ links): the event log read is one page of 500. A longer log can leave a later phase unmarked; the README says so.
- Next steps: open the PR. Do not treat a simulated monitoring event as a live check.
- Warnings for the next session: the branch was created tracking `origin/main`. Push with an explicit refspec.

---

### 2026-10-17 - Alan (Claude) - standards addendum P0, SEC-002, SEC-006, SEC-008, M3
- **Did:** Codex had moved the standards catalogs to `standards/` (#74). New branch `feat/alan/standards-roe-wiring` off main carried only the agent side. It was merged as #100 (`831edfa`). Changes: a rules-of-engagement gate in `ToolRegistry.invoke` (SCOPE_DENIED plus `tool.roe_denied`); the RoE is issued at SCOPE_CHECK and re-issued on host resume. Scout validates the CWE and takes its OWASP API tag from code. Trace proposes the eight CVSS v3.1 metrics with evidence; code computes the level (ADR-0012). Trace carries an optional validated ATT&CK id, and Diagnose and Fortify an optional D3FEND id. Added the offline report and smoke commands. Follow-up PR #103 adds an opt-in live seven-role smoke and partial M3 evidence.
- **State of the code:** replay/offline only. No live seven-role run has been observed. The demo finding is now CVSS 3.1 base 6.5 medium; labels.yaml says high.
- **Commands run:** `cd security-agents && .venv/bin/python -m pytest tests -q` gave 442 passed, 10 skipped. `cd standards && pytest tests -q` gave 189 passed. `python -m security_agents.standards.report` gave 217 passed, 0 failed. Smoke wrote 3 files.
- **Decisions:** ADR-0012 (CVSS v3.1 sets the level; v4.0 alongside). RQ-016 answered (proposed).
- **Open questions:** Srihith decides the v3.1 shared field (Option A or B) and the RoE endpoint. Adam decides on CWE-840 (Prohibited) in labels.yaml.
- **Next steps:** a key holder runs the live seven-role smoke (message `alan-to-srihith-adam-live-seven-role-run`). After M3: SARIF 2.1.0, SP 800-61 alignment, OWASP LLM self-assessment.
- **Warnings:** macOS keeps re-hiding the venv `.pth` files; set `PYTHONPATH=.:../shared:../standards:../code-intelligence:../examples/payments-lite/target`. Do not merge the old `feat/alan/seven-agent-runtime` branch; it carries duplicate catalogs.

### 2026-10-17 — Alan — verify honesty + CheckCategory
- **Did:** New branch `feat/alan/verify-honesty-check-category` off current main after #83 merged. Did not push `feat/alan/host-resume-hardening`. Honesty: kept #84's `provider_mode="none"` for functional Verify (did not merge #71/`mode=functional` while #85 is open). `_pinned_snapshot` already uses `SCHEMA_INVALID`; added a regression test. Canonical `CheckCategory` in `shared` 0.9.0 with Probe ids + V0 fixture aliases; scope_guard treats aliases as equal. Message to Srihith posted.
- **State of the code:** Fixture `AuthorizedScope.json` values unchanged. Probe templates unchanged.
- **Commands run:** `uv run pytest -q shared/tests/test_contracts.py security-agents/tests/test_scope_guard.py security-agents/tests/test_verify_followups.py security-agents/tests/test_host_adapter.py security-agents/tests/test_functional_verification_guards.py security-agents/tests/test_contracts.py` → **128 passed**, 1 skipped (`tsc` not on PATH). Frontend CI follow-up: `npm ci --prefix frontend/transport && npm ci --prefix frontend && npm run build --prefix frontend/transport && npm run typecheck --prefix frontend` (pass); `npm test --prefix frontend/transport` (27 pass); `npm run lint --prefix frontend` (pass). Local `npm test --prefix frontend` failed to start Vitest workers (Node v22.14 vs undici requiring ≥22.19; CI uses Node 24).
- **Decisions:** Honest option = label `none` (Srihith #84), not a fake/live Verify agent turn. Do not take #71's verify.py rewrite.
- **Next steps:** Land this PR; Srihith ACK of CheckCategory; #85 can land independently.
- **Warnings:** Do not push merged branches. Skip live Anthropic / Docker. Do not edit Adam's CWE-840 labels.

### 2026-10-17 — Alan — Codex P1/P2 host-resume hardening after #73
- **Did:** #73 merged to main. Did **not** push to `feat/alan/host-finding-persistence`. Diffed Codex P1/P2 against `origin/main` (`236838e`): all seven items were missing. New branch `feat/alan/host-resume-hardening` off current main. Implemented: resume `host.repo_id` filter; `claim_checkpoint` (assessment row lock, consume); finish Verify before `record_verification`; truncated pytest lists rejected; `external_pending` includes already-approved functional work; full recipe `target_dir` strip; persist `patch_rejected`. Asked to close #35 (do not merge).
- **State of the code:** Hosted resume is single-winner per checkpoint; functional Verify publishes only after the run finishes.
- **Commands run:** `uv run pytest -q security-agents/tests/test_host_adapter.py security-agents/tests/test_functional_verification_guards.py security-agents/tests/test_e2e_replay.py backend/tests/test_e2e_host.py backend/tests/test_intelligence_memory_api.py` → **82 passed**.
- **Decisions:** Follow-up PR rather than amending the merged branch. Did not merge #71 or #35.
- **Next steps:** Land the follow-up PR; close #35.
- **Warnings:** Do not push to `feat/alan/host-finding-persistence`. Do not merge #35 or #71.

### 2026-10-17 — Alan — port c75a56e pause gates onto #73
- **Did:** Ported Srihith follow-up `c75a56e` (not #71): `_report_or_wait` for early security exits; unconditional pause while `external_pending`; kept existing `_functional_reproduced` complete-run rule (no error / not timed out / pytest exit 1) and added the hang/`exit_code=None` case.
- **State of the code:** Standalone orchestrator now walks RECON→…→AWAITING_APPROVAL when a functional approval is owed; security auto-approve no longer skips a pending functional gate.
- **Commands run:** `uv run pytest -q security-agents/tests/test_host_adapter.py security-agents/tests/test_e2e_replay.py security-agents/tests/test_functional_verification_guards.py` → **68 passed** in 114s.
- **Decisions:** Did not merge #71; did not take `verify.py` `_functional_reproduction` or `compute_verdict` masking.
- **Next steps:** Reply on PR #73 comment; remaining Codex P1/P2 on #73 still open except this follow-up.
- **Warnings:** Do not merge #71.

### 2026-10-17 — Alan — host finding persistence, durable resume, functional Verify
- **Did:** New branch `feat/alan/host-finding-persistence` off current main. Did **not** continue `feat/alan/security-standards` (already on main via #49/#57/#69) and did **not** merge PR #35. Host adapter now: (1) `set_finding_status` from orchestrator status/patch/verify/fortify; (2) durable `save_checkpoint`/`load_checkpoint` (salvaged from #35, dropped its duplicate `standards/` and weaker `llm/schema.py`); (3) Sai's `request_functional_approvals` / `repair_approved_functional_findings` / `functional_verification_inputs` with `Orchestrator.external_pending`; (4) `tool_calls` + `sandbox_seconds` on the assessment ledger.
- **State of the code:** Fake-provider unified assessment: security finding `hardened` with full history; functional finding `verified` with five passing checks; resume after `pipeline._ORCHESTRATORS.clear()`. Live Anthropic still unverified (issue #10). Docker sandbox still UNVERIFIED (INFRA-005).
- **Commands run:** `make check` (ruff + shared export/examples); `uv run pytest -q security-agents/tests/test_host_adapter.py backend/tests/test_unified_assessment.py backend/tests/test_security_agents_host_mode.py backend/tests/test_e2e_host.py` → **27 passed**.
- **Decisions:** Functional Verify verdict is computed from executed tests, not an LLM turn (`llm_calls=0` on `functional-verify:*` runs). PR #35 should be closed, not rebased.
- **Next steps:** Draft PR to main; comment on #35 to close; Vihaan re-check finding status in the UI.
- **Warnings:** Do not merge #35. Do not reopen `feat/alan/security-standards`. CWE-840 on payments-lite labels is Adam's file.

### 2026-10-17 — Alan implementation agent — standards follow-up after #49/#57
- **Did:** Merged `origin/main` (Srihith's #57 already landed catalogs, incidents API, OWASP 2025/2026 matrices, producer CWE validators). Follow-up on `feat/alan/security-standards`: `Finding.standards.cvss` is now derived from recorded Probe/Trace facts via `standards.cvss_assess` (LLM eleven-metric dict stays provisional on `SeverityAssessment.cvss` only). Fortify D3FEND is copied onto `Finding.standards.d3fend`. Orchestrator `_classify` + `public()["standards"]`. LLM07:2025 coverage moved `gap` → `partial` with a system-prompt secret-shape scan. ACK'd Sai's CWE-adjudication review. Did not touch `frontend/` or add incident APIs (already on main).
- **State of the code:** One planted IDOR (CWE-639 / T1190 / fact-derived CVSS / D3-AMED proposed) classified in the fake-provider e2e replay. Not certification or compliance.
- **Commands run:** see the follow-up PR body (actual pytest output).
- **Decisions:** Authoritative CVSS is never the model's metric dict. Recorded attack-path preconditions map to CVSS AT:P.
- **Next steps:** Srihith ACK of the host-integration assertion change; frontend already renders `Finding.standards` via Vihaan's pages.
- **Warnings:** Do not claim the LLM cannot leak a system prompt; the new test only asserts prompts contain no secret-shaped literals.

### 2026-10-16 — Claude Code (development agent) — DOCS-003
- **Did:** Added interim proprietary `LICENSE` (all rights reserved) at the owner's
  request; updated LICENSE-DECISION.md, README status, task board, CHANGELOG. Set the
  GitHub repo description and topics. Corrected the INFRA-001 note below.
- **State of the code:** Still no application code.
- **Next steps:** Revisit the long-term license before the repo is made public.

### 2026-10-16 — Claude Code (development agent) — DOCS-001, INFRA-001
- **Did:** Completed Phase 0. Wrote docs 00–26, `architecture/`, `agents/`,
  `prompts/`, `planning/`, `decisions/` (template + ADRs 0001–0010, all
  *Proposed*), `research/`; READMEs for all eleven top-level code directories.
  Pushed to the private GitHub repo `adamissac/hackatl-agentic-security`, which
  had already been created with the base commit (`a59f0a8`) by the repository owner.
- **State of the code:** No application code exists. Only Markdown, repository
  config files and GitHub templates. Verified with a file listing of non-Markdown
  files.
- **Commands run:** internal Markdown link check (script, not committed) — all
  links resolve; secret-pattern scan over the tree — no matches beyond
  placeholders in `.env.example`.
- **Decisions:** All architecture choices recorded as *Proposed* ADRs pending
  team ratification (DOCS-002).
- **Assumptions:** Doc numbers 02, 03, 14, 18–22, 26 were not named by the
  original README/AGENTS/CLAUDE files; titles chosen from context (e.g. 14 = UX,
  18 = infrastructure per `.env.example`, 20 = demo, 26 = risks for architecture
  review). Demo target name `payments-lite` is a proposal.
- **Open questions:** RQ-011 (HackATL date/format), RQ-014 (team), and the rest
  of [RESEARCH_QUESTIONS](../research/RESEARCH_QUESTIONS.md).
- **Next steps:** Human authorizes Phase 1; assign roles; ratify ADRs; start
  CORE-001, DEMO-001, RL-001, INFRA-003, INFRA-005 in parallel.
- **Warnings:** Do not start Phase 1 work without explicit authorization. CI
  link/secret checks are not automated yet (INFRA-003).


### 2026-10-17 — Sarosh implementation agent — INTEL-001..008, PR #6

- Implemented persistent SHA-pinned Python intelligence on `feat/sarosh/code-intelligence`.
  Git object reads never execute target code; include_prefix excludes labels/answer keys.
  Tree-sitter/AST structure, static graph confidence, route dependencies, extracted intent,
  optional bounded Claude inference, delimited context and symbol-span impact are implemented.
- Uses canonical shared models, SQLite local and backend-owned PostgreSQL PayloadStore.
  Real signed-webhook integration persisted symbol-level head impact.
- Executed: producer/PostgreSQL **22 passed, 1 opt-in skip**; broader shared/monitoring/backend/
  intelligence **105 passed, 4 skipped** (RL package, TypeScript compiler, two live suites).
  Ruff/format/strict mypy pass; 337 Markdown files checked, 0 link problems.
- Actual-target evidence and canonical ContextPack fixture are in `code-intelligence/evidence`
  and `code-intelligence/fixtures`; small labeled exact graph TP=3 FP=0 FN=0.
- Live attempt skipped because authorized key unavailable here. FakeTransport exercised the
  shared gateway, denied a shell tool and persisted low-confidence inference metadata.
- Next: sync latest main and final CI; Sai/Alan replace temporary runtime indexing with this
  service. Human decisions, promoted regression/finding joins, router composition and parse
  caching remain follow-ups. No full runtime or production claim. Unrelated untracked
  `.serena/` and nested checkout were left untouched.

- Sarosh final verification (2026-10-17T01:56Z): on main sync `4a8d692`, broader suite
  **113 passed, 4 skipped** with isolated TypeScript 5.6.3 compiler. Skips: RL-dependent
  collection/test and two live suites. Intelligence/store/webhook acceptance previously
  **22 passed, 1 skipped**; subsequent actual factory/exclusivity check passed. PR CI for
  pushed `87e898d`: both test jobs, links and gitleaks passed. Check latest PR #6 revision
  and consumer adapter messages before further integration.

- Sarosh final failure-path check (2026-10-17T01:59Z): producer/PostgreSQL/webhook suite
  **23 passed, 1 opt-in skip**; invalid commit/path ingestion returns terminal failed
  Snapshot for the backend to persist. Ruff/format/strict mypy pass. PR #6 carries final
  commits and CI status; live inference remains blocked on an authorized key.

- Sarosh ownership review fix (2026-10-17T02:03Z): route-specific ownership rules and
  sibling-call-site evidence now reach the vulnerable payment read; get_store is not auth.
  A two-commit actual-target test proves the possible-inconsistency warning disappears when
  require_owner is restored. Broader suite: **115 passed, 4 skipped**. Index version 0.2.0
  requires re-indexing old 0.1.0 payloads; all fact/source keys remain immutable. Updated
  producer evidence/context fixture have 49 expectations and a 23,267 / 24,000 pack.

- Sarosh merged producer (2026-10-17T02:06:06Z): PR #6 → `bcc2e23`, exact tested tree
  `d608af5`. Final CI passed both test jobs, links and gitleaks. Final focused suite:
  **24 passed, 1 skipped**; broader suite: **115 passed, 4 skipped**. Consumers should pull
  main and re-index at python-ast-ts/0.2.0. Full reviewer/security pipeline proof and live
  inference remain outstanding; see the immutable merged-producer message.

### 2026-10-17 — Sarosh / Codex — UI-001/UI-003 transport assistance

- User authorized isolated help in unfinished lanes and frequent direct main commits.
  Reserved only `frontend/transport/**` in issue #29; no remote Vihaan branch or
  scaffold existed at each milestone check. No app, backend or shared source edits.
- Implemented standalone strict TS/ESM package consuming canonical generated types
  and JSON schemas. Session/CSRF, explicit approvals, idempotency, lists/logout,
  bounded JSON and SSE, Last-Event-ID resume, retries, abort and terminal-state
  verification. API contract mismatches found by integration were fixed.
- Executed `npm test --prefix frontend/transport`: 13 passed plus strict TS build.
  `npm run test:integration --prefix frontend/transport`: 4 passed (parent + 3
  subtests) against real FastAPI and isolated PostgreSQL; zero model calls/target
  executions. Ruff/format of Python harness passed. Initially mislabeled 4-pass
  status corrected explicitly: first unit run was 3 passed/1 failed, later fixed.
- Commits: `d4a0fce`, `3bc4e28`, `05ce162`, `a48a202`; pushed main per user direction.
- Next: Vihaan adopts file dependency and connects pages; Adam/Vihaan wire transport
  commands into frontend CI. Browser CORS/cookies/rendered behavior remain unverified.
- Sai's real-index consumer integration merged PR #31. Sarosh attempted its test
  but collection failed because local environment lacks installed `code_review`;
  no independent consumer-pass claim. Producer suite was rechecked separately.

### 2026-10-17T04:35Z — Sarosh recovered intelligence-memory continuation (PR #39)

- Recovered the Codex worktree `/tmp/hackatl-sarosh-memory` on
  `feat/sarosh/intelligence-memory`; no work was discarded. Fixed the CI failure
  in `PostgresMemoryStore.decisions` (partitioned `expectation_id` was not in the
  subquery select) and the new test's use of string agent names.
- Merged `origin/main` through `dd9f8a9`, preserving Sai's functional-remediation
  changes. Kept the reviewer only on Sai's paths (`_runner` shared-intelligence
  hook plus one test-double check) and added Alan's host adapter wiring as a small
  isolated hook.
- Implemented durable accepted-Verify -> verified-regression outbox, exact-snapshot
  host snapshot attachment, shared hosted intelligence service use, context/API
  surfacing, and all-five-check enforcement at the trusted host boundary.
- Executed on the merged tree: backend/shared/monitoring/reviewer **154 passed,
  5 skipped**; code-intelligence/shared **62 passed, 2 skipped**; code-review
  **48 passed, 1 skipped**; security-agents **344 passed, 11 skipped**; focused
  memory/host tests **7 passed**. Ruff/format changed paths, strict mypy for
  root/code-intelligence/code-review, contract freshness (92 files, 0 changed),
  and 223-document link check passed.
- Remaining gate: Srihith's contract-owner ACK of additive schema 0.6.0 on #38/PR
  #39. Live provider, RL package, browser/app e2e and full hardened deployment
  remain separate prerequisites; no such claim is made here.

## 2026-10-17 — standards integration (Srihith)

Continued from PR37 prompt on branch `feat/srihith/standards-alignment`. Read GitHub and adopted Alan PR49 canonical0.7 contracts/catalogs/scoring/lifecycle rather than a competing schema. Added real backend incident persistence/API/approval/evidence/audit gates, report standards, host atomic classification updates, producer integration, dual OWASP2025/2026 coverage and transport helpers. New migration0005. Contract generation fresh. Root193 passed/2 live skips; security/reviewer400 passed/11 optional skips; RL82 passed; transport16 unit+4 real-stack tests. No paid calls, deployment or infrastructure response. Review stacked PR before merge; coordinate frontend page mounting with Vihaan and other standards additions with Alan.

Final review follow-up: added strict regression artifact/hash proof, succeeded-Verify requirement, and demo incident labels; model CVSS interpretations are provisional assumptions rather than claimed verified metrics. Adopted Alan’s additional canonical tests/CI at80fb0e7. Expanded root suite304 passed/2 live skips; separate migration coexistence and incident suite5 passed after allocating revision0005_incidents (avoids PR39’s0005). Final standalone tests include standards126, security/reviewer400, RL82 and transport16+4.

### 2026-10-17 — Codex — isolated recovered catalog additions
- Recovered Claude dirty-worktree changes without discarding any work. Saved checkpoint 93c0225 and tested recovery on PR #35.
- Merged PR #69 after observing all checks pass. New PR #73 supplies a narrower host recovery/functional-Verify path, so unique catalog additions are isolated on feat/alan/recovered-catalogs; duplicate legacy runtime catalogs from #35 are excluded.
- New canonical modules: CVSS3.1 base scoring, OWASP API2023 project mappings, NIST800-115 headings and explicit source-hash refresh tool. No shared schema change. NVD terms retain their existing unverified label.
- Saved previous broad verification evidence in coordination/status/ALAN.md; rerun checks on this branch before merge.

## 2026-10-17 — frontend expectations / incidents / settings pages (Devin for Adam)

Branch `devin/1792226026-frontend-gaps` (merged `origin/main` at efc0e55). Frontend owner idle; these routes were specified in docs/14 with backend APIs already on main. Added transport `expectations`, `decideExpectation`, `expectationDecisions`, `updateProject` (PATCH; additive, no contract change) and pages `/projects/[id]/expectations`, `/incidents`, `/settings`. Executed: transport 27 passed; app ESLint, tsc, Vitest 29 passed, Next build; browser e2e via `tests/e2e/stack.py` 11 passed (3 new) against real FastAPI + PostgreSQL + worker with scripted (non-live) model transports. Not done: incident closure/lessons-learned/evidence-link UI, functional-remediation pause/resume (Alan #73), live provider, Docker sandbox proof.

### 2026-10-17 — Codex — functional verification safety and recovery consolidation
- Continued newer Alan PR #73 rather than landing duplicate legacy runtime standards from PR #35. Unique recovered canonical catalog code is PR #74 (189 offline tests). PR #69 merged.
- Tightened independent functional verification: empty test bundles, runner/collection errors, timeout, skipped tests and fabricated sandbox evidence cannot pass. Generated tests cannot replace existing files. Resume rechecks current scope and binds the active host/job.
- Adopted only PR #71's two-remediation browser fixture. Both security and functional fixes complete through the actual API/queue/worker/DB stack using scripted model replies.
- Commands/results: root pytest 324 passed/6 optional skips; security pytest 379 passed/11 optional skips; focused authorization/evidence guards36 passed; PostgreSQL subset11 passed; browser8 passed; Ruff/format/mypy pass.
- No live-model call, hardened Docker execution, deployment or always-on operation was performed.

## 2026-10-17 — frontend expectations / incidents / settings pages (Devin for Adam)

Branch `devin/1792226026-frontend-gaps` (merged `origin/main` at efc0e55). Frontend owner idle; these routes were specified in docs/14 with backend APIs already on main. Added transport `expectations`, `decideExpectation`, `expectationDecisions`, `updateProject` (PATCH; additive, no contract change) and pages `/projects/[id]/expectations`, `/incidents`, `/settings`. Executed: transport 27 passed; app ESLint, tsc, Vitest 29 passed, Next build; browser e2e via `tests/e2e/stack.py` 11 passed (3 new) against real FastAPI + PostgreSQL + worker with scripted (non-live) model transports. Not done: incident closure/lessons-learned/evidence-link UI, functional-remediation pause/resume (Alan #73), live provider, Docker sandbox proof.

## 2026-10-17 — incident closure UI (Devin for Adam)

Branch `devin/*-incident-closure` from main after #80. Added `components/incident-closure.tsx` (link finding / accepted verification, add + satisfy closure criteria with hash-pinned patch-diff or Fortify regression artifacts, lessons learned, communications, closure readiness) and pure helpers in `lib/incidents.ts`. Executed: tsc, ESLint, Vitest 32 passed, real-stack Playwright incl. new closure spec. Found (not fixed, other lanes): no producer sets `HardeningRecommendation.proposed_test_artifact_id`, so lessons learned → closure is unreachable for hosted assessments; see coordination/messages/20261017T093000Z-adam-to-alan-srihith-fortify-regression-artifact.md.

## 2026-10-17 — REG-001 complete: Devin closure evidence continuation

Branch `fix/srihith/fortify-closure-artifacts`, based on merged Devin PRs80/81 and Alan PR83. Real security and functional Verify now retain bounded, unchanged regression sources as redacted ArtifactStore archives and publish their actual canonical hardening artifact IDs. Incident eradication resolves remediation-plan approval to the same finding/project/assessment. Evidence selectors now accept options that arrive after linking a finding.

Executed: focused host/unified/verification/closure54 passed; root325 passed/7 skips (optional RL dependency, global tsc unavailable, opt-in live providers); security-agent396 passed/11 optional skips; frontend32 unit tests; real PostgreSQL/API/worker/Chrome browser12 passed, including complete two-person incident lifecycle through Closed and reload. ESLint, TypeScript, production build, Ruff/format, mypy and generated contracts110-file freshness passed. Browser runs use scripted transports; no paid provider calls, deployment or individual test-node execution claim.

### 2026-10-17 — recovered catalog integration refresh
Synced PR74 with current main after PR83/85/87, preserving both task histories and changelog entries. Corrected README: CVSS3.1 is an explicit reference calculator, while runtime severity retains CVSS4.0. Standards189 passed, manifest integrity and Ruff/format pass. No live data refresh or provider call.

### 2026-10-17 — QA-001: finish unexecuted Devin QA tools
Replaced invalid imports/nonexistent npm commands and skip-as-success summaries in PR94’s proposal. Scripts use the current interpreter, do not install dependencies, force live model evals off, resolve paths independently of cwd, and execute existing suites. Added runner semantics CI. Executed on the proposal base: helper10 passed; security wrapper backend/monitoring/reviewer/intelligence162 passed/7 optional skips and security-agent394 passed/11 optional skips; frontend wrapper transport/tsc/lint/build/Vitest32 and actual-stack Chrome12 passed. Preflight from /tmp and optional RL runner intentionally return2 (incomplete: no Docker, RL package, or persistent API on this machine). No paid calls or deployment. Readiness report now records evidence and points to current milestones rather than stale blockers.
