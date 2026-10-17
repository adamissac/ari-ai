# hackatl-agentic-security

> **Status: implementation in progress.**
> Runtime packages and integration tests now exist. Specifications still describe
> capabilities beyond the implemented scope. See
> [Current implementation status](#current-implementation-status).

An autonomous software engineering and cybersecurity platform, being built for
HackATL and intended to grow into a real product.

**The one-line concept:** an AI engineering team that understands your software,
makes sure it works correctly, challenges its security, repairs verified problems,
and keeps defending it after deployment.

## The three pillars

| Pillar | Question it answers | Spec |
|---|---|---|
| 1. Code intelligence, review & repair | *Does the software actually work the way it is supposed to?* | [05](docs/05_CODE_INTELLIGENCE_ENGINE.md), [06](docs/06_CODE_REVIEW_AND_REPAIR.md) |
| 2. Seven-agent cybersecurity team | *Even if it works, can an attacker exploit it?* | [07](docs/07_SEVEN_AGENT_CYBERTEAM.md), [08](docs/08_AGENT_ORCHESTRATION.md), [agents/](docs/agents/AGENT_CONTRACT.md) |
| 3. Continuous monitoring & RL defense | *As the software changes and runs, how do we keep it secure?* | [09](docs/09_RL_DEFENSE_SYSTEM.md), [10](docs/10_CONTINUOUS_MONITORING.md), [17](docs/17_RL_EVALUATION_PROTOCOL.md) |

The pillars are **not** three products in one dashboard. They share one
version-aware **Unified Intelligence Layer** ([11](docs/11_SHARED_CONTEXT_AND_MEMORY.md))
and one closed loop:

```
UNDERSTAND → REVIEW → TEST → ATTACK SAFELY → DIAGNOSE → REPAIR → VERIFY → MONITOR → LEARN → REPEAT
```

## The seven runtime security agents

| # | Agent | Team | Role |
|---|---|---|---|
| 1 | Scout | Red | Reconnaissance; produces evidence-backed vulnerability *hypotheses* |
| 2 | Probe | Red | Validates hypotheses with non-destructive tests in authorized sandboxes |
| 3 | Trace | Red | Attack-path and impact analysis; labels unverified steps as hypotheses |
| 4 | Diagnose | Blue | Root cause and remediation strategy, grounded in intended behavior |
| 5 | Patch | Blue | Candidate fix in an isolated worktree; never merges or deploys |
| 6 | Fortify | Blue | Hardening and prevention recommendations, regression tests |
| 7 | Verify | Independent | Re-runs the exploit and functional tests; accepts or rejects on evidence |

These are **product runtime agents**. They are distinct from the *development*
coding agents (Claude Code etc.) that build this repository — see
[AGENTS.md](AGENTS.md) and [docs/prompts/](docs/prompts/00_MASTER_ENGINEERING_PROMPT.md).

## Where to start

1. [docs/00_START_HERE.md](docs/00_START_HERE.md) — reading order for humans.
2. [CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md) — mandatory orientation for coding agents.
3. [docs/01_MASTER_PRODUCT_SPEC.md](docs/01_MASTER_PRODUCT_SPEC.md) — what we are building.
4. [docs/04_SYSTEM_ARCHITECTURE.md](docs/04_SYSTEM_ARCHITECTURE.md) — how it fits together.
5. [docs/planning/HACKATL_TASKS.md](docs/planning/HACKATL_TASKS.md) — what to build next.

## Repository layout

```
docs/               Specifications, architecture, agent contracts, planning, research
frontend/           Next.js + TypeScript dashboard (not yet implemented)
backend/            FastAPI control-plane API (not yet implemented)
code-intelligence/  Repository indexing, symbol/call graphs, retrieval (not yet implemented)
code-review/        Functional review + candidate repair engine (not yet implemented)
security-agents/    Seven-agent runtime + orchestrator + tool registry (not yet implemented)
rl-defense/         Gymnasium env, Double DQN, baselines, evaluation (not yet implemented)
monitoring/         Event ingestion, correlation, scheduling (not yet implemented)
shared/             Cross-subsystem contracts (Pydantic → JSON Schema → TS) (not yet implemented)
tests/              Cross-subsystem integration / e2e suites (not yet implemented)
scripts/            Developer tooling (not yet implemented)
examples/           Deliberately vulnerable demo targets (not yet implemented)
```

Each directory's README defines its future responsibilities, interfaces, and dependencies.

## Proposed stack (to be validated — see [ADRs](docs/decisions/README.md))

Next.js · React · TypeScript · Tailwind | Python · FastAPI · Pydantic v2 |
Anthropic Claude (model id configurable, initial target `claude-opus-5-5`) |
Tree-sitter | PostgreSQL | Docker-isolated sandboxes | PyTorch · Gymnasium · Double DQN |
Vercel (frontend) · Railway (backend) — not provisioned.

## Current implementation status

| Area | Status |
|---|---|
| Repository skeleton, docs, shared contracts (Pydantic + generated JSON Schema/TS) | ✅ |
| Backend (FastAPI + PostgreSQL), worker, monitoring ingestion, incidents API | ✅ implemented, tested locally and in CI |
| Code intelligence, functional reviewer, seven runtime security agents | ✅ implemented; live-model runs are opt-in |
| RL defense (simulation-only DDQN, evaluation bundles) | ✅ implemented; recommendations are never applied automatically |
| Frontend console (assessments, findings, approvals, scopes, expectations, monitoring, incidents, settings, Defense Lab) | ✅ implemented; browser e2e against the real local stack with scripted (non-live) model transports |
| Functional remediation pause/resume, hardened Docker sandbox proof, unified M7 demo | 🚧 in progress (see [coordination/MILESTONES.md](coordination/MILESTONES.md)) |
| CI | ✅ GitHub Actions workflows in [.github/workflows](.github/workflows) |
| Infrastructure / deployment | ❌ Not provisioned |
| License | Proprietary, all rights reserved (interim) — [LICENSE](LICENSE), [LICENSE-DECISION.md](LICENSE-DECISION.md) |

## Contributing & security

See [CONTRIBUTING.md](CONTRIBUTING.md), [docs/24_DEVELOPMENT_STANDARDS.md](docs/24_DEVELOPMENT_STANDARDS.md),
and [SECURITY.md](SECURITY.md). This project builds offensive-security tooling;
**all security testing must target only explicitly authorized, isolated environments**
([docs/15_SECURITY_BOUNDARIES.md](docs/15_SECURITY_BOUNDARIES.md)).

## Standards alignment

Versioned ATT&CK/D3FEND/CWE catalogs, deterministic CVSS 4.0, persisted incident handling aligned to NIST SP 800-61r3, and OWASP LLM Top 10 2025/2026 platform self-assessments are implemented on this branch. See [standards](standards/README.md), [incident handling](docs/security/NIST_INCIDENT_HANDLING.md), and [OWASP coverage](docs/security/OWASP_LLM_TOP10_COVERAGE.md). Controls have explicit gaps; these are not certification or comprehensive detection claims. The frontend renders the incident lifecycle, approval gates and simulated-drill labels. No production containment is executed.
