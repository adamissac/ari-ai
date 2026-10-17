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

## 2026-10-17 — frontend expectations / incidents / settings pages (Devin for Adam)

Branch `devin/1792226026-frontend-gaps` (merged `origin/main` at efc0e55). Frontend owner idle; these routes were specified in docs/14 with backend APIs already on main. Added transport `expectations`, `decideExpectation`, `expectationDecisions`, `updateProject` (PATCH; additive, no contract change) and pages `/projects/[id]/expectations`, `/incidents`, `/settings`. Executed: transport 27 passed; app ESLint, tsc, Vitest 29 passed, Next build; browser e2e via `tests/e2e/stack.py` 11 passed (3 new) against real FastAPI + PostgreSQL + worker with scripted (non-live) model transports. Not done: incident closure/lessons-learned/evidence-link UI, functional-remediation pause/resume (Alan #73), live provider, Docker sandbox proof.

## 2026-10-17 — incident closure UI (Devin for Adam)

Branch `devin/*-incident-closure` from main after #80. Added `components/incident-closure.tsx` (link finding / accepted verification, add + satisfy closure criteria with hash-pinned patch-diff or Fortify regression artifacts, lessons learned, communications, closure readiness) and pure helpers in `lib/incidents.ts`. Executed: tsc, ESLint, Vitest 32 passed, real-stack Playwright incl. new closure spec. Found (not fixed, other lanes): no producer sets `HardeningRecommendation.proposed_test_artifact_id`, so lessons learned → closure is unreachable for hosted assessments; see coordination/messages/20261017T093000Z-adam-to-alan-srihith-fortify-regression-artifact.md.
