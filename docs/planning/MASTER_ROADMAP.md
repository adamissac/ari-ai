# Master roadmap

**Current phase: implementation authorized (2026-10-16).** Phase 0 is complete; Phases
1–5 proceed as six parallel owner tracks per [MASTER_BUILD_SPEC](../../MASTER_BUILD_SPEC.md)
and milestones M0–M8 in [coordination/MILESTONES](../../coordination/MILESTONES.md).
Deployment, paid infrastructure and production actions still need explicit human approval. HackATL event date is unconfirmed
(RQ-011); durations below are relative and must be fitted once it is known.

| Phase | Name | Goal | Exit criteria | Key tasks |
|---|---|---|---|---|
| 0 | Repository & architecture | Shared understanding, contracts as docs, task plan | Docs complete, links resolve, private repo pushed | DOCS-001, INFRA-001 |
| 1 | Foundations & walking skeleton | Runnable skeleton, contracts in code, CI, sandbox driver, demo target | IC-1, IC-2 green; ADRs ratified | CORE-001…010, SEC-001…003, UI-001, INFRA-002…005, DEMO-001, TEST-001, TEST-002, DOCS-002 |
| 2 | Understand & review (P1) | Index demo target, expectations, functional finding proven, repair verified | IC-3, IC-5 green | INTEL-001…008, REVIEW-001…003 |
| 3 | Security team (P2) | Seven agents on the demo target with sandbox boundaries | IC-4, IC-6 green; SB suite green | SEC-004…013, TEST-003, TEST-004 |
| 4 | Monitor & learn (P3) | Change-driven re-assessment; RL evaluated per protocol | IC-7, IC-8 green | MON-001…004, RL-001…005 |
| 5 | Integration & HackATL demo | One reliable storyline | IC-9 green; rehearsal checklist done | UI-002…007, TEST-005, DEMO-002, DEMO-003 |
| 6 | Post-hackathon | Product hardening, design partners | Defined after HackATL retrospective | [BACKLOG](BACKLOG.md) |

## Parallelism

Phases 2, 3 and 4 are **tracks**, not strictly sequential: once Phase 1 exits,
P1, P2 and P3 work proceeds in parallel against fixtures
([25](../25_INTEGRATION_STRATEGY.md)). RL-001…004 have no platform dependencies
and can start as soon as Phase 1 is authorized.

## Phase gates

Each phase transition requires: exit criteria met (with evidence), task board
updated, SESSION_HANDOFF entry, and a human "go" recorded in this file.

| Phase | Started | Completed | Authorized by |
|---|---|---|---|
| 0 | 2026-10-16 | 2026-10-16 | Repository owner |
| 1–5 | 2026-10-16 | — | Repository owner (implementation pack) |
