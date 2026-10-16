# ADR-0003: Deterministic state-machine orchestrator

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-16 |
| Deciders | UNASSIGNED (ratify in DOCS-002) |
| Related | [08](../08_AGENT_ORCHESTRATION.md), SEC-012 |

## Context
Seven agents with different privileges must run in order with gates (scope, approval, budget). LLM-planned multi-agent conversations are hard to test, replay and constrain.

## Decision
The orchestrator is a Python state machine persisted in PostgreSQL. LLMs may rank or summarize but never choose transitions, grant permissions or skip gates. Agents exchange typed artifacts by ID, not conversations.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| Deterministic state machine | Testable, replayable, safe gates | New workflows require code changes |
| LLM planner/router | Flexible | Non-deterministic; injection can alter control flow |
| Workflow engine (Temporal) | Durable execution | Extra infrastructure for MVP |

## Consequences
- Every transition can be unit-tested and audited.
- Recorded runs can be replayed with a FakeLLM.
- Temporal remains an option behind the same state definitions.

## Revisit when
Workflows need long-running durable timers/human tasks beyond what the DB-backed machine handles cleanly.
