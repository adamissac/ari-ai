# Changelog

All notable changes are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions will follow
[Semantic Versioning](https://semver.org/) once releases begin.

## [Unreleased]

### Fixed
- Hosted assessments with a still-pending functional approval now pause at
  `AWAITING_APPROVAL` even when security work ended early or was already
  approved. Early security exits walk skipped phases to the only legal pause
  edge (`DIAGNOSIS` → `AWAITING_APPROVAL`) instead of completing.
- Approval resume re-applies the `host.repo_id` target filter, atomically claims
  the checkpoint so two workers cannot both Patch/Verify, finishes the Verify run
  before publishing a verdict, rejects truncated pytest failure lists, treats
  already-approved functional findings as outstanding work, strips the complete
  recipe `target_dir`, and persists `patch_rejected` when functional Verify is
  not accepted.
- Functional Verify stays labelled `provider_mode="none"` (no model call). An
  escaping `build_recipe.json` `target_dir` raises `SCHEMA_INVALID`.

### Added
- Canonical `CheckCategory` in `shared` (schema 0.9.0): Probe library ids
  `access_control.ownership` / `input_validation.bounds`, with published V0
  fixture aliases `authorization.ownership` / `input.bounds`. Scope matching
  treats each pair as the same category.
- Frontend: incident closure panel (link findings/verifications, closure criteria with artifact evidence, lessons learned, communications, readiness list).
- Hosted assessments persist security finding lifecycle (`hypothesis → … → hardened`),
  durable approval checkpoints (`save_checkpoint` / `load_checkpoint` so a worker
  restart can resume), and approval-gated functional repair plus independent Verify.
  Assessment usage now includes `tool_calls` and `sandbox_seconds` from host runs.
  Fake-provider only; live seven-agent path still unverified (no Anthropic key).
- Frontend console pages on existing backend APIs: **Expectations** (snapshot-pinned behavioral
  expectations with confirm/conflicting/reject decisions, optimistic `expected_revision` and
  decision history), **Incidents** (NIST SP 800-61r3 lifecycle, triage, owner, two-person
  approval gates, simulated-drill labels, timeline) and **Settings** (default and monitoring
  budgets, trigger policy). Transport gains `expectations`, `decideExpectation`,
  `expectationDecisions` and `updateProject` (PATCH).
- Exact-snapshot human intent decisions (`confirmed`/`conflicting`/`rejected`) with
  authenticated backend routes, append-only revisions and `human_input` provenance.
- Independently verified candidate-regression memory: accepted Verify results with all
  five unique checks enqueue a durable, idempotent regression join and surface through
  context packs and the shared hosted intelligence adapter. Candidate evidence only;
  never a merge/current-SHA claim.
- Security-agent findings now attach an evidence-derived `Finding.standards` view (catalog CWE, reviewed ATT&CK/D3FEND rules, CVSS v4.0 from recorded facts). Trace's optional metric dict is a provisional annotation only. Not a certification or compliance claim.
- Standards integration: pinned ATT&CK/D3FEND/CWE, deterministic CVSS 4.0, NIST SP 800-61r3 incident APIs with persisted evidence and approval gates, OWASP LLM Top 10 2025/2026 self-assessments, and frontend transport support. No certification or autonomous containment claims.
- Standalone frontend REST/SSE transport with canonical schema validation, cookie/CSRF auth, idempotency, durable event resume and real FastAPI/PostgreSQL integration tests. Page integration remains pending.
- Phase 0 repository foundation: product specification, system architecture,
  seven runtime agent contracts, RL defense design and evaluation protocol,
  shared context design, data contracts, API design, UX design, security
  boundaries, testing strategy, planning (roadmap, MVP scope, task board, backlog,
  dependencies, definition of done, handoffs), development-agent prompts, ADR
  template and proposed ADRs, research plan, GitHub templates.
- Interim proprietary `LICENSE` (all rights reserved); see `LICENSE-DECISION.md`.

### Added (rl-defense, branch `feat/adam/rl-defense`)
- `DefenseSimEnv-v0`, Double DQN training, baselines, protocol-17 evaluation and
  simulation-derived recommendation adapter; reference results in `rl-defense/results/`.

### Added (code intelligence, PR #6)
- Persistent Python intelligence at an immutable Git SHA: symbols, static call/import
  graph, route dependencies, source-cited behavioral intent, bounded context packs and
  two-version impact. SQLite and backend PostgreSQL share one payload port.
- Optional bounded Claude-gateway inference with validated citations, low confidence
  and persisted provider metadata; FakeTransport CI coverage.

### Not yet implemented
- Full cross-pillar runtime completion and production operation are not established here.
