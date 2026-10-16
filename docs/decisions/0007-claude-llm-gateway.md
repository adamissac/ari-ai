# ADR-0007: Anthropic Claude behind a single LLM gateway

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-16 |
| Deciders | UNASSIGNED (ratify in DOCS-002) |
| Related | [19](../19_OBSERVABILITY_AND_COST_CONTROL.md), CORE-010 |

## Context
Agents and review need strong code reasoning and structured output. Cost, logging, redaction and budgets must be enforced uniformly.

## Decision
All model calls go through one gateway module. Default model id from `ANTHROPIC_MODEL` (initial target `claude-opus-5-5`, availability to be verified), optional `ANTHROPIC_MODEL_FAST` for triage/summaries, per-agent overrides via `AGENT_MODEL_OVERRIDES`. The gateway enforces budgets, redacts secrets, records requests/responses, validates structured outputs and supports record/replay.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| Single gateway, Claude default | Uniform controls; model swap by config | Gateway is a critical dependency |
| Direct SDK calls per agent | Simple | Inconsistent budgets/logging |
| Multi-provider abstraction now | Vendor flexibility | Lowest-common-denominator features; more work |

## Consequences
- Model ids are configuration, never hard-coded in agents.
- Replay mode makes tests and demos independent of the API.

## Revisit when
Model availability, pricing or capability changes; need for a second provider.
