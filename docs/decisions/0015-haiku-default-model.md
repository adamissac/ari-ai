# ADR-0015: Claude Haiku 5.5 is the default model for every Anthropic call

| Field | Value |
|---|---|
| Status | Accepted (implemented in #340) |
| Date | 2026-10-19 |
| Deciders | Adam (product owner) |
| Related | ADR-0007 (Claude LLM gateway), #340, #341, `backend/backend/settings.py`, `security-agents/security_agents/llm/gateway.py`, `frontend/lib/live-analysis.ts` |

## Context
Every Anthropic request (seven security agents, code reviewer, frontend live commit analysis)
defaulted to Claude Opus 5.5 ($4 / $20 per million input / output tokens). The product owner
asked for Claude Haiku 5.5 ($0.10 / $0.50 per million tokens for prompts up to 100K) to cut cost.

## Decision
1. `claude-haiku-5-5` is the default in the backend gateway, the security-agents gateway and the
   frontend live analysis.
2. `ANTHROPIC_MODEL` and `AGENT_MODEL_OVERRIDES` still override it per deployment or per agent; Opus
   is one environment variable away (`ANTHROPIC_MODEL=claude-opus-5-5`).
3. Haiku has no server-side refusal fallback, so the `fallbacks` parameter is not sent for
   `claude-haiku-*`. Nothing silently reroutes a request to a more expensive model.
4. Cost accounting prices the model actually used (per-model tables), so budgets stay correct
   under any override.

## Consequences
- Much lower spend per assessment and per commit analysis.
- **No quality re-evaluation at Haiku has been run.** The live seven-agent comparison (#325) was
  measured on Opus 5.5; its results do not transfer to Haiku. Haiku is a smaller model, and agent
  success rates may differ. Re-run the comparison before making quality claims at the new default.
- Specs that named Opus as the default (MASTER_BUILD_SPEC, docs/07, docs/18) now point here.
