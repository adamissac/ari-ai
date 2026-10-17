# Sarosh — implementation status

Owner: Sarosh
Branch: feat/sarosh/intelligence-handoff (implementation feat/sarosh/code-intelligence merged)
Current task: INTEL-001 through INTEL-008 producer merged (#6); consumer/runtime handoff
Last remote sync: 2026-10-17T02:07:54Z; main d194132 (contracts 0.4.0), implementation PR #6 merged bcc2e23
API/contract dependencies: canonical shared models and backend PostgreSQL PayloadStore integrated from main; consumer runtime adapters pending
Verified tests: 24 passed/1 opt-in skip focused; 115 passed/4 skipped broader; Ruff/format/strict mypy (11 modules) and final PR CI passed
Recent PR/commit: PR #6 merged bcc2e23; ownership fix 10fd408; PostgreSQL/gateway 99cbc4c
Blockers: authorized live Claude key unavailable here; full reviewer/security runtime adoption belongs to consumer integration
Next action: Sai/Alan integrate current-version producer contexts; live smoke requires authorized key.

## Session entries

Add dated factual entries; do not overwrite history. Never claim unexecuted tests passed.

- 2026-10-17T01:03Z: Read master/personalized instructions, inspected remote branches and shared V0 models. Published API/persistence proposal; package initialized. No runtime test claim yet. Existing untracked `.serena/` and nested checkout are unrelated and excluded.
- 2026-10-17T01:08Z: `.venv/bin/pytest -o addopts='' code-intelligence/tests -q` passed 4 tests; `.venv/bin/ruff check code-intelligence` passed; `.venv/bin/mypy --config-file code-intelligence/pyproject.toml code-intelligence/code_intelligence` passed 8 modules. Ingestion, Tree-sitter syntax validation, AST extraction, static graph, FastAPI/Flask declarations, extracted test/docstring intent implemented. SQLite/service/retrieval code written; dedicated integration tests follow. No live LLM call or backend persistence claim.
- 2026-10-17T01:48Z: Merged main through `41fb569` into feature branch. Added `INTELLIGENCE_PAYLOAD_STORE_FACTORY=backend.intel_store:build_payload_store`; relaxed pathspec upper bound and retained workspace mypy 2.4.0. `.venv/bin/pytest -o addopts='' code-intelligence/tests backend/tests/test_intel_store.py backend/tests/test_intel_integration.py -ra` → **19 passed, 1 skipped** against real PostgreSQL. Signed webhook recorded symbol-level impact from persisted two-commit indexes. FakeTransport inference test exercised two gateway turns, denied shell tool, persisted model/usage/tool records and low-confidence expectations. `RUN_LIVE_LLM_EVAL=1 ... -m live_llm` skipped: authorized Anthropic key unavailable in this workspace; no live inference claim.

- 2026-10-17T01:53Z: Producer acceptance plus real PostgreSQL suites: **22 passed, 1 live opt-in skip**. Broader shared/monitoring/backend/intelligence run: **105 passed, 4 skipped** (RL not installed, TypeScript compiler absent, two live suites). Ruff/format and strict mypy pass (11 modules). Markdown links: 337 files, 0 problems. Context fixture generated from owned target SHA `41fb569c791d1775a02bf1d385ea6903f4210d27`: 12 chunks, conservative count 23,154 within 24,000. Labeled fixture exact edges TP=3 FP=0 FN=0; no general accuracy claim. Full Sai/Alan runtime adapters and live inference remain unverified; authenticated human-intent decisions remain backend follow-up. Next: sync latest main, final checks and PR #6 CI.

- 2026-10-17T01:56Z: Synced main through `4a8d692` (contracts 0.3.0/runtime ingestion), then `TSC=/tmp/sarosh-intel-ts/node_modules/.bin/tsc .venv/bin/pytest -o addopts='' shared/tests monitoring/tests backend/tests code-intelligence/tests -ra` → **113 passed, 4 skipped**. TypeScript schema consumer test passed with isolated compiler; skips are RL-dependent modules/test plus two live suites. Final bounded-ingestion/ancestor-ignore and actual PostgreSQL factory checks pass. PR CI for prior pushed revision: both test jobs, links and gitleaks passed; final push follows. Consumer message and canonical fixture published; waiting on complete reviewer/security runtime adoption and authorized live key for full integration evidence.

- 2026-10-17T01:59Z: Final producer/PostgreSQL/webhook acceptance **23 passed, 1 opt-in skip** after adding terminal `Snapshot.failed` for invalid commit/path ingestion. Backend can persist this failure instead of leaving the snapshot pending. Final Ruff/format/strict mypy pass; PR CI for `eb1067a` passed both test jobs, links and gitleaks. Final failure-path commit and latest-main sync follow; exact final head/CI in PR #6.

- 2026-10-17T02:03Z: Addressed Adam's cross-pillar review: route-attached module ownership intent plus sibling ownership-check inconsistency with exact call-site citations; get_store excluded from auth_dependencies; in-body require_owner recorded. Actual-target two-commit test proves warning disappears after the missing check is added. Broader suite **115 passed, 4 skipped**; own suite **19 passed, 1 skipped** before version-only refresh. INDEX_VERSION bumped to python-ast-ts/0.2.0, so old caches cannot masquerade as improved current facts. Regenerated canonical fixture: 49 expectations; 12 context chunks; conservative count 23,267 / 24,000. Final combined refresh follows in PR #6.

- 2026-10-17T02:06:06Z: PR #6 **MERGED** as `bcc2e23389f147b82feef2bdac50f60965b7d350`. Final CI (both test jobs, links, gitleaks) passed for `d608af5`; `git diff --quiet HEAD origin/main` confirmed merged tree identity. Final focused tests **24 passed, 1 skipped**; broader tests **115 passed, 4 skipped**. Core implementation commits include `99cbc4c` (PostgreSQL/gateway), `87e898d` (evidence/CI), `cd24eda` (terminal failures), `10fd408` (reviewed ownership correction). Handoff message publishes current index 0.2.0 and re-index requirement. No live/complete consumer runtime claim.

- 2026-10-17T02:07:54Z: Synced contracts 0.4.0 / hosted backend adapter (`d194132`). ID schema change allows underscores/hyphens; producer DTO fields are unchanged. Re-executed focused producer/PostgreSQL/webhook suite: **24 passed, 1 skipped**. No intelligence source changes required. Documentation handoff PR #21 records merged status; full consumer use of this producer remains a separate runtime evidence gate.

- 2026-10-17T02:54Z: User authorized isolated help in unfinished lanes and frequent main commits. Reserved `frontend/transport/**` for portable REST/SSE support to Vihaan in issue #29; no frontend app scaffold/backend/shared edits. First REST step: canonical runtime schema validation, session/CSRF, explicit approvals, idempotency headers and bounded JSON. `npm test --prefix frontend/transport`: CORRECTION: initial run was 3 passed / 1 failed (synchronous-throw assertion); earlier command sequence masked that failure. Strict TypeScript build passed. Corrected assertion and full rerun recorded below. SSE and real-backend proof follow; M6 remains incomplete.
- 2026-10-17T02:57Z: Corrected synchronous-throw assertion, then `npm test --prefix frontend/transport` exited 0: **11 passed, 0 failed**, strict TypeScript compilation passed. Added validated SSE, durable cursor resume/deduplication, bounded retry, abort/cancellation and persisted terminal-state confirmation. This is fixture transport proof; real FastAPI/PostgreSQL proof follows. Corrected previous mistaken 4-pass entry explicitly above.
- 2026-10-17T03:00Z: Real HTTP integration exited 0: **4 Node tests passed (one parent + three subtests)** against FastAPI + isolated real PostgreSQL. Proved persisted session/project, CSRF refusal, other-tenant 404, separate-human scope approval, idempotency replay/conflict, queued cancellation and durable SSE seqs 1/2/3 with resume 2/3 and empty terminal resume confirmation. Zero model calls/target executions. Fixed creation-envelope mismatch and early terminal-state SSE stop found by this run. Main commits `d4a0fce`, `3bc4e28` pushed; initial entry timestamps corrected to actual UTC clock (immutable reservation filename retained).
- 2026-10-17T03:03Z: Added canonical validated project/repository/scope/assessment/run/finding/approval lists and explicit logout, session reset, missing-idempotency-key guard. `npm test --prefix frontend/transport`: **13 passed, 0 failed**, strict build passed. `npm run test:integration --prefix frontend/transport`: **4 passed, 0 failed** including real list responses/logout. Python harness Ruff/format passed; isolated test databases dropped. Latest concurrent reviewer sandbox changes integrated without modifying them.
- 2026-10-17T03:04Z: Final producer verification on integrated main: `.venv/bin/pytest -o addopts='' code-intelligence/tests -m 'not live_llm' --junitxml=/tmp/sarosh-intelligence-current.xml` → **19 passed, 1 deselected**. Separate attempt to collect Sai's `code-review/tests/test_intel_integration.py` failed with missing installed `code_review`; his PR #31 evidence is acknowledged but not independently claimed. Transport integration re-run with active SSE abort: **4 passed**. No changes to other owners' product lanes. Remaining action: Vihaan app integration/browser proof and frontend CI adoption; issue #29 tracks handoff.
- 2026-10-17T03:05Z: Documentation/handoff complete; `scripts/check_links.py` checked **369 Markdown files, 0 problems**. GitHub issue #29 published the executable transport handoff; PR #31 received same-session index-consumer acknowledgment. No new frontend branch/overlap appeared in final remote check. App/browser/CI acceptance remains explicitly pending.
- 2026-10-17T03:10Z: Readiness sweep on main `9be2623`: **39 shared contract tests passed**, including generated TS compile. Reproduced Docker COPY-input dependency-plan failure (Python 3.12, exit 2, omitted code-intelligence/review workspace paths), filed backend packaging issue. Published remaining software vs external-prerequisite inventory in `20261017T031045Z-sarosh-to-all-readiness-sweep.md`. UI/app, pending Srihith runtime fixes, human-intent API/regression intelligence joins and full hardened unified e2e remain; not a human-only finish list. No product edits.
- 2026-10-17T03:36Z: User authorized finishing all feasible remaining work. Synced `72213a7`; runtime fixes are merged and Vihaan has active frontend work (no frontend edits by me). Claimed packaging #34, proposed canonical human-intent/regression contract #38. Docker COPY-input tests now **2 passed**; added actual image/non-root/no-network CI proof (pending execution). `.dockerignore` excludes local secrets/artifacts. Next: durable intelligence memory while owner reviews additive contract.
- Intelligence-memory branch: append-only SQLite decisions with optimistic concurrency/history; effective expectations and bounded packets reflect authenticated human evidence for review/Scout/Trace/Verify/monitoring. Independent candidate regression registration requires all five checks and separate producing run, exact base SHA; source index remains immutable. Focused new + shared suite **44 passed**; full producer **22 passed, 1 deselected**. Strict producer mypy (12 modules)/Ruff passed after tuple typing correction. Sai ACK #38 received, added public `verified_regressions(ref)` as requested. Backend PostgreSQL/auth wiring in progress; contract owner ack pending in draft PR #39.
- PostgreSQL/auth memory step: **2 passed** on real PostgreSQL/API. Tenant 404, CSRF 403, actor spoof 422, optimistic concurrency 409, idempotent retry, one atomic chained audit entry, restart/context/status/history reads and append-only SQL trigger denial verified. Membership enforced in adapter as well as HTTP. Dedicated migration 0005; immutable source payloads unchanged. Backend/producer/shared Ruff+format and strict producer mypy passed. Contract owner review requested on PR #39; no canonical schema landed on main without ack.
- 2026-10-17T04:35Z: Continued recovered Codex work on `feat/sarosh/intelligence-memory`; fixed the failing PostgreSQL decisions query by selecting the partitioned `expectation_id`, and corrected the new host test to pass canonical `AgentName` values. Merged `origin/main` through `dd9f8a9` and integrated with Sai's remediation/runtime changes without reverting his work. Added verified-regression durable outbox, host attachment/service APIs, shared hosted intelligence adapter, and all-five-check enforcement at the trusted host boundary. Full executed suites on the merged tree: backend/shared/monitoring/reviewer **154 passed, 5 skipped**; code-intelligence/shared **62 passed, 2 skipped**; code-review **48 passed, 1 skipped**; security-agents **344 passed, 11 skipped**; focused memory/host tests **7 passed**. Skips are opt-in live provider, RL package/TypeScript compiler, and sandbox-only tests. Ruff/format on changed paths, root/code-intelligence/code-review strict mypy, generated contracts (92 files, 0 changed) and 223-document link check passed. PR #39 updated; Srihith contract-owner ACK is the remaining merge gate.
- 2026-10-17T04:45Z: Sent the PR #39 merge-hold communication to all owners (`coordination/messages/20261017T044521Z-sarosh-to-all-pr39-hold-for-ack.md`). Branch `4b9fc39` is green and mergeable; waiting only on Srihith's contract-owner ACK for schema 0.6.0. No direct-to-main push; merge will go through PR #39 after ACK/counter.
- 2026-10-17T13:30Z: Resumed from recovered handoff #145; #39/#38 complete, memory smoke **8 passed** on current main. Found/reproduced #148 (same-SHA ingestion cache ignored prefix/limits and could bypass invalid-prefix validation). Fix branch `fix/sarosh/intelligence-scope-cache` uses normalized profile-aware index versions (base 0.3.0) and exact stored provenance. New producer **6 passed**; broad producer/shared/PostgreSQL **97 passed, 1 opt-in live skip**; added real PostgreSQL profile **1 passed**; hosted M7/unified/reviewer consumer **11 passed** using scripted test transports. Strict producer mypy/Ruff/format passed. Historical refs/decisions immutable, no cross-profile confirmation carry. No duplicate #39 work or active owner edits.
- 2026-10-17T13:22Z: PR #39 was merged by Adam as `2ab5584` (issue #38 closed); no unmerged lane commits remain. Fast-forwarded the recovered worktree to `origin/main` `39186cb`, ran `uv sync --frozen`, and re-ran focused memory/contract tests **8 passed** plus regression/host/reviewer integration **11 passed**. Published the Codex resume brief at `coordination/messages/20261017T132209Z-sarosh-to-codex-recovered-memory-handoff.md`.

- 2026-10-17T13:45Z: Ingestion profile fix #150 merged as `1129434` (product `5015d67`, tested head `91cea8c`); #148 closed. All executable CI checks green: backend417/8skip, producer33/1skip, reviewer60/3skip, security455/18skip, Docker security6/reviewer2, Vitest67/browser12. Exact commands and scoped migration are in PR #150. Published final owner-gate/consumer handoff; no live-provider or deployment claim.

- 2026-10-17T14:21Z: Owner requested consultation with Sai before placing the supplied Ari ant logo. Published original unchanged at `frontend/public/brand/ari-ant.png` on `feat/sarosh/ari-logo` (`9f43c95`); source/copy SHA-256 match. Requested placement/dark-light/intro guidance in issue #165, tagged Sai on #164, and published immutable coordination request. No UI placement changed while waiting for a reply. Existing brand suites6 passed; `npm run typecheck` passed. No identifiable local Sai session; resume on actual #165 reply or supplied agent channel.

- 2026-10-17T14:39Z: Actual Sai guidance received in #165/#176 and applied to #169: shared 24px header/sign-in, 96px intro700ms fade, app/icon.png; no extra landing/story/graph/footer marks. Original bytes preserved. Unit71, tsc/lint and provisional focused browser2 passed; final combined checks pending. Earlier unreachable/default status is superseded by actual sign-off.

- 2026-10-17T14:42Z: #169 actual Sai-approved placement verified on main3799984 combined tree: unit71, tsc/lint/build passed; real-stack Chrome/PostgreSQL/API/worker browser14 passed(47.9s), final screenshot-focused browser2 passed(13.6s). Desktop1440x1000/mobile390x844; source/icon hashes match original, intro/session/reduced-motion/header checks pass. CI merge gate next. Story-card overflow routed to #156; no full-page-width/live-provider/deployment claim.

- 2026-10-17T14:52Z: #169 merged as `b38b6ff`; #165 closed. Actual Sai-approved surfaces complete. Product598bf2c/tested4b48388: CI unit71/browser14/build/types/lint/docs/gitleaks green; CI browser passed on retry after pre-browser font-pipeline failure without source changes. Local full14 + focused2 pass; original PNGs byte-identical. Published final Sai handoff; reserved UI files released. No deployment/live-provider claim.

- 2026-10-17T15:16Z: Owner requested ten-minute maintenance/coordination loop while active. First cycle synced164e0c8; ACK later bare-ant #186/#189 and leave UI #156/#187/#188 untouched. Isolated worktree /tmp/hackatl-sarosh-maintenance, branch feat/sarosh/intelligence-maintenance. Auditing context-pack free-form metadata; no bug/test claim yet.

- 2026-10-17T15:23Z: Maintenance cycle1 reproduced #190 with fake bearer canary in context citation metadata and public expectation source notes. Output-copy redaction implemented; identity fields, authenticated history and immutable index bytes preserved. Focused10, producer/shared/PostgreSQL107 passed/1 opt-in live skip, hosted reviewer/security/M7 consumer11 passed. Ruff/format and strict producer mypy12 modules passed. No actual credential/provider/third-party action. PR/CI next.

- 2026-10-17T15:35Z: Cycle2/3 #190/#196 merged4119eff, all CI green. Reproduced #199 false exact call from beyond-package relative import to unrelated root helper. Parser0.3.1 keeps unresolved spelling and diagnostic; valid nested/init/aliased imports preserved. Focused15, broad producer/shared/PostgreSQL123 passed/1 opt-in skip, hosted reviewer/security/M7 consumer11 passed67.42s; mypy12/Ruff/format passed. Old refs/history immutable, active reindex required. Read-only font review188 approved e7cde76 after manifest/license presence and green checks; latest author commits require their own review. No UI edits. Next ten-minute read15:44:40Z.
- 2026-10-17T15:53Z: Took over the active relative-import work from the prior Codex session in `/private/tmp/hackatl-sarosh-import-grounding`. Merged current `origin/main` (`a696361`) cleanly, reran focused/privacy **25 passed**, broader producer/shared/PostgreSQL **122 passed, 2 skipped**, hosted reviewer/security/M7 consumer **11 passed**, Ruff/format, strict producer mypy (12 modules), 345-document links and `git diff --check`. Polished user-facing changelog/README/task wording. PR #201 is mergeable with green CI; no product-code behavior changed beyond the already-described parser 0.3.1 fix.

## 2026-10-17T18:45:19+00:00 — Sarosh: ARI frontend polish (local)

Branch: `feat/sarosh/ari-frontend-polish` in `/tmp/ari-website-polish`, based on
`e715ac7` from `adamissac/ari-ai` (owner corrected the original slide-deck URL).
Updated header/hero/brand/pricing copy/metadata, one local font plus license/hash,
and related unit/browser checks. Kept ant assets and existing body/display/mono fonts.

Executed: `npm run lint --prefix frontend`; `npm run typecheck --prefix frontend`;
`NEXT_PUBLIC_DEMO_ONLY=1 npm run build --prefix frontend` (all passed);
`npm test --prefix frontend -- --maxWorkers=2` (49 files, 211 tests passed);
`E2E_BASE_URL=http://127.0.0.1:3015 E2E_DEMO_ONLY=1 E2E_BROWSER_CHANNEL=chrome ARI_LANDING_SCREENSHOTS=/tmp/ari-polish-screens npm run e2e --prefix frontend -- tests/e2e/landing.spec.ts --reporter=list` (5 passed).
Default parallel unit rerun hit one existing logo-file test's 5s timeout under concurrent
build load; rerun with 2 workers passed without changing any timeouts.
Rendered Chrome inspection covered desktop/mobile hero and scrolled light/dark content;
no browser warnings/errors observed. Screenshots/logs are outside Git under `/tmp/ari-polish-*`.
The full authenticated backend e2e suite was not run. No provider calls, API changes,
push, merge or deployment. Next action: review local diff; publish via reviewed branch
only when authorized (Git-connected pushes create Vercel previews).

## 2026-10-17T19:01:17+00:00 — Sarosh: transparent navigation and warm headline refinement

Local branch `feat/sarosh/ari-frontend-polish` in `/tmp/ari-website-polish`; integrated
current main (`f81ab5a`) before changes. Removed logo/link cards, borders and shadows;
ordinary links have subtle translucent hover fills. Pricing alone retains a solid accent.
`HeaderContrast` samples the painted surface beneath each control, adapting white/ink
text and the ant over hero, light chapters, later dark chapters and light cards.
Uses passive scroll/resize listeners and coalesced animation frames; attributes change
only when the tone changes. No dependencies or geometry/link changes.

Headline content, structure, CTAs, workflow pills, spacing and background are untouched.
Only its text styling gains a warm off-white core and three diffuse ember shadows.
The dimmest core exceeds 4.7:1 against the solid brand color (unit assertion);
no added filter or animation.

Executed: transport build; `npm run lint --prefix frontend`; `npm run typecheck --prefix frontend`;
`npm test --prefix frontend -- --maxWorkers=2` (50 files, 215 passed);
`NEXT_PUBLIC_DEMO_ONLY=1 npm run build --prefix frontend` (passed);
`E2E_BASE_URL=http://127.0.0.1:3015 E2E_DEMO_ONLY=1 E2E_BROWSER_CHANNEL=chrome ARI_LANDING_SCREENSHOTS=/tmp/ari-nav-glow-screens npm run e2e --prefix frontend -- tests/e2e/landing.spec.ts --reporter=list`
(5 passed, 25.4s; 1440/1024/390/320px plus reduced motion). Verified transparent
controls, dark/light/later-dark contrast, hover, 44px targets, routes, no overflow, warm
headline styling and retained content. Corrected a browser-test race that interrupted
the smooth anchor animation before checking the next scroll position.
Rendered desktop/mobile and scrolled light views inspected; no browser warnings/errors
observed. Full authenticated backend e2e not rerun. No push, merge to main or deployment.
Screenshots and logs remain external to Git at `/tmp/ari-nav-glow-*` and `/tmp/ari-nav-*`.
Next action: review local commit and authorize publishing if desired.

## 2026-10-17T19:10:13+00:00 — Sarosh: homepage navigation scroll reveal (local)

Branch `feat/sarosh/ari-frontend-polish`, `/tmp/ari-website-polish`. Integrated
main through `0f645c2`, preserving Sai's refreshed README and the newer local ARI
branding/font details during its sole merge conflict.

`SiteNavigation` reveals Projects/Defense Lab/Demo/Pricing at `scrollY >= 100`,
independent of direction, and hides them below it. Group geometry remains reserved;
logo/account remain visible and Sign In's x/y stay unchanged. Hidden group uses
`inert`, `aria-hidden`, visibility and pointer blocking. Transition: 250ms fade +8px
horizontal offset, removed for reduced motion. Other routes always show all links.
The checkout had no separate mobile menu, so added a compact phone Menu disclosure
with Escape/focus restoration; crossing the threshold closes it. No hero/content,
headline, font, background, workflow, CTA, backend or API changes.

Executed: `npm run lint --prefix frontend`; `npm run typecheck --prefix frontend`;
`npm test --prefix frontend -- --maxWorkers=2` (51 files, 219 passed);
`NEXT_PUBLIC_DEMO_ONLY=1 npm run build --prefix frontend` (passed);
`E2E_BASE_URL=http://127.0.0.1:3015 E2E_DEMO_ONLY=1 E2E_BROWSER_CHANNEL=chrome ARI_LANDING_SCREENSHOTS=/tmp/ari-reveal-screens npm run e2e --prefix frontend -- tests/e2e/landing.spec.ts --reporter=list`
(5 passed, 36.6s, 1440/1024/390/320px and reduced motion). Browser assertions prove
0/99 hidden, 100 shown, decreasing above threshold shown, returning to zero hidden,
hidden-focus rejection, phone menu/Escape, unchanged account coordinates, no overflow
and full navigation on pricing. Desktop/mobile top and revealed screenshots inspected.
Existing brand e2e scroll checkpoint updated from 80px to 120px; its full backend
suite was not rerun. Screenshots external to Git: `/tmp/ari-reveal-screens`.
No push or deployment. Next action: review local commit; publishing remains pending.

## 2026-10-17T19:14:09+00:00 — Owner-authorized publication to main

The owner explicitly requested pushing the accumulated frontend changes to main.
Product commits: `391831a`, `ed37e30`, `b2961f9`; current main base: `0f645c2`.
Scope: ARI branding, local wordmark font, centered warm headline, transparent
contrast-aware navigation and homepage 100px reveal with phone Menu access.
Final unchanged product tree passed lint, type-check, demo-only production build,
219 unit tests (51 files, two workers) and 5 Chromium browser tests (36.6s), covering
1440/1024/390/320px, reduced motion, top/reveal/return, inert focus and anchored account.
No backend/API changes in the publication diff. Earlier local-only notes describe
the state before this authorization. Publishing via a normal fast-forward push;
next action is to confirm GitHub main matches the release commit and inspect CI.
The Git-connected Vercel deployment is triggered by that push; no project settings changed.
