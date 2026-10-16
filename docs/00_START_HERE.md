# 00 — Start here

> **Phase 0.** Everything under `docs/` describes the *intended* system. Nothing
> here is implemented yet. When a doc says "the orchestrator does X", read it as
> "the orchestrator **will** do X once built".

## What this project is in one paragraph

A platform that connects to a software repository and acts like a small,
disciplined engineering and security team. It learns what the code does and is
**supposed** to do, checks that it actually does that, challenges it with
authorized adversarial testing inside sandboxes, proposes fixes for problems it
can prove, independently verifies those fixes by running them, and keeps
watching the software as it changes. Every claim it makes is backed by evidence
that a human can inspect.

## Reading order

### Everyone (≈ 45 minutes)

1. [01 Master product spec](01_MASTER_PRODUCT_SPEC.md) — what and why.
2. [02 Problem and users](02_PROBLEM_AND_USERS.md) — who it is for.
3. [04 System architecture](04_SYSTEM_ARCHITECTURE.md) — the four planes and the closed loop.
4. [11 Shared context and memory](11_SHARED_CONTEXT_AND_MEMORY.md) — the differentiator.
5. [15 Security boundaries](15_SECURITY_BOUNDARIES.md) — the rules nobody may break.
6. [planning/MVP_SCOPE](planning/MVP_SCOPE.md) and [planning/HACKATL_TASKS](planning/HACKATL_TASKS.md) — what we build first.
7. [22 Glossary](22_GLOSSARY.md) — keep it open.

### Then, by role

| You will work on | Read next |
|---|---|
| Frontend | [14](14_FRONTEND_UX_DESIGN.md), [13](13_BACKEND_API_DESIGN.md), [12](12_DATA_MODELS_AND_CONTRACTS.md) |
| Backend / platform | [13](13_BACKEND_API_DESIGN.md), [12](12_DATA_MODELS_AND_CONTRACTS.md), [18](18_INFRASTRUCTURE_AND_DEPLOYMENT.md), [19](19_OBSERVABILITY_AND_COST_CONTROL.md) |
| Code intelligence | [05](05_CODE_INTELLIGENCE_ENGINE.md), [architecture/code-intelligence](architecture/code-intelligence.md) |
| Review & repair | [06](06_CODE_REVIEW_AND_REPAIR.md), [16](16_TESTING_AND_VERIFICATION.md) |
| Security agents | [07](07_SEVEN_AGENT_CYBERTEAM.md), [08](08_AGENT_ORCHESTRATION.md), [agents/AGENT_CONTRACT](agents/AGENT_CONTRACT.md), [architecture/sandbox-and-authorization](architecture/sandbox-and-authorization.md) |
| RL defense | [09](09_RL_DEFENSE_SYSTEM.md), [17](17_RL_EVALUATION_PROTOCOL.md), [architecture/rl-training-and-inference](architecture/rl-training-and-inference.md) |
| Monitoring / integrations | [10](10_CONTINUOUS_MONITORING.md), [25](25_INTEGRATION_STRATEGY.md), [architecture/event-lifecycle](architecture/event-lifecycle.md) |
| Testing | [16](16_TESTING_AND_VERIFICATION.md), [17](17_RL_EVALUATION_PROTOCOL.md) |
| Demo / pitch | [20](20_DEMO_SCRIPT.md), [21](21_COMPETITIVE_LANDSCAPE.md) |

New team members should also follow [23 Team onboarding](23_TEAM_ONBOARDING.md).
Coding agents start at [CLAUDE.md](../CLAUDE.md) / [AGENTS.md](../AGENTS.md).

## Map of `docs/`

| Range | Contents |
|---|---|
| 00–03 | Orientation, product spec, users, requirements |
| 04–11 | Architecture of the platform and each pillar |
| 12–14 | Contracts: data models, API, UX |
| 15–17 | Safety, testing, RL evaluation |
| 18–19 | Infrastructure, observability, cost |
| 20–22 | Demo, competitive landscape, glossary |
| 23–26 | Onboarding, standards, integration, risks |
| [architecture/](architecture/README.md) | Deep-dive diagrams and lifecycles |
| [agents/](agents/AGENT_CONTRACT.md) | One contract per runtime security agent |
| [prompts/](prompts/README.md) | Role prompts for *development* agents |
| [planning/](planning/README.md) | Roadmap, tasks, dependencies, handoffs |
| [decisions/](decisions/README.md) | Architecture Decision Records |
| [research/](research/README.md) | Open questions and research plan |

## Vocabulary you must get right

- **Implemented / specified / proposed / hypothesis** — always say which.
- **Runtime agent** (Scout … Verify, a product feature) vs **development agent**
  (Claude Code etc., which builds this repo).
- **Finding** (an evidence-backed problem) vs **hypothesis** (a suspicion not yet
  validated).
- **Authorized scope** — the only set of targets the platform may ever test.
