# ADR-0025: The code reviewer runs on Claude Sonnet 5.5 in production

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-10 |
| Deciders | Adam (product owner) |
| Related | ADR-0015 (Haiku default), `backend/backend/settings.py`, `code-review/eval/REVIEWER_MODEL_COMPARISON_2026-11-10.md` |

## Context
ADR-0015 fixed every production/staging agent to `claude-haiku-5-5` and noted that no quality
evaluation had been run at Haiku. The live comparison of 2026-11-10 ran the reviewer on 11
multi-file corpus cases: Haiku located 5-6 of 8 defects and raised a finding on a clean
ownership refactor in 3 of 3 runs; Sonnet 5.5 and Opus 5.5 located 7-8 with no false positive.
Sonnet matched Opus at under half the cost. The owner approved the switch for the reviewer.

## Decision
In production and staging `Settings.model_for("reviewer")` returns `claude-sonnet-5-5`. Every
other agent stays on `claude-haiku-5-5`. The choice is still fixed in code: `ANTHROPIC_MODEL`
and `AGENT_MODEL_OVERRIDES` are ignored outside development/test.

## Consequences
- Reviewer token cost rises about 11 times (measured: $0.004 to $0.043 per corpus review). The
  per-assessment and daily spend caps are unchanged and still bound it.
- Sonnet supports the server-side refusal fallback, so reviewer requests now send
  `fallbacks` when `LLM_SERVER_FALLBACKS` is on. ADR-0015 point 3 holds for Haiku agents only.
- The evidence is 11 small Python cases, 2-3 runs per model. It does not cover the seven
  security agents, and it has not been repeated on the production pipeline.
