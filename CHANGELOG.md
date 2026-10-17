# Changelog

All notable changes are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions will follow
[Semantic Versioning](https://semver.org/) once releases begin.

## [Unreleased]

- Consolidated CVSS v3.1, OWASP API 2023 and NIST SP 800-115 runtime references into the canonical offline standards package.

- Security assessments can resume their approval pause on a fresh worker using an integrity-checked persisted checkpoint.

- Hosted security runs now persist gateway usage and real patch/Verify run IDs; host scope adaptation fails closed and Docker is the default sandbox.

- Security agents now project numeric tool schemas for provider compatibility and fail assessments when Scout fails.

### Added
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
