# Changelog

All notable changes are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions will follow
[Semantic Versioning](https://semver.org/) once releases begin.

## [Unreleased]

- An assessment page lists Understand, Review, Security test, Repair, and Verify from that check's event log. Monitoring stays on the project page.
- An assessment page leads with one sentence for its recorded state. A finished check is not described as a secure application.
- Defense Lab replay names the highest recorded alert rate at the current step and the recorded action. It does not show the hidden attacker stage.
- A project page shows six phases of the latest check. A phase is completed only when that check's event log shows it was entered, and a verification verdict comes from the finding list.
- Defense Lab replay leads with one sentence from the recorded episode: first and last action, whether it was marked compromised, and which nodes reached impact. The metrics charts follow that replay.
- Finding detail leads with a before-and-after story taken from the recorded title, severity, validation, patch, and verification. It does not claim a fix worked without a verdict.
- Source links use the assessment scope's repository when that scope names exactly one, so a project can hold more than one repo.
- A project page leads with one next step and three counts taken from the assessments, findings, scopes and monitoring flag already loaded. It does not invent a security score.
- Finding detail shows the indexed expectation statement for each linked id, and keeps the id when that snapshot has no matching statement.

- Hosted security and functional verification retain actual regression sources as hash-pinned artifacts; incident lessons learned can cite them. Plan-bound security approvals are resolved through persisted finding/assessment records for incident eradication.

- Added canonical offline CVSS v3.1, OWASP API 2023 and NIST SP 800-115 reference catalogs with integrity checks and pinned-source refresh tooling.

- QA scripts execute the existing suites and preserve failed versus incomplete results; preflight no longer declares demo readiness from warnings.

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
- Assessment page shows each runtime agent with the job it does, only the runs and tool calls that were recorded, and what is still open for the next agent.
- Finding detail shows the persisted standards view (CWE, CVSS, ATT&CK, D3FEND) as text, including when nothing was assessed.
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
