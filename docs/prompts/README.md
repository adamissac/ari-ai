# Development-agent prompts

These are prompts for **development agents** (Claude Code, Codex, Cursor…)
that build this repository. They are **not** prompts for the product's runtime
agents — those live with the code in `security-agents/` once implemented.

## How to use

1. Paste or reference [00_MASTER_ENGINEERING_PROMPT](00_MASTER_ENGINEERING_PROMPT.md)
   (or rely on CLAUDE.md/AGENTS.md being loaded).
2. Add the role prompt for the work type.
3. Add the task: `Task: <ID> from docs/planning/HACKATL_TASKS.md`.

| Prompt | Use for |
|---|---|
| [00 Master engineering prompt](00_MASTER_ENGINEERING_PROMPT.md) | Dense context for any session |
| [01 Frontend engineer](01_FRONTEND_ENGINEER.md) | `frontend/` |
| [02 Backend engineer](02_BACKEND_ENGINEER.md) | `backend/`, persistence, jobs |
| [03 Code intelligence engineer](03_CODE_INTELLIGENCE_ENGINEER.md) | `code-intelligence/` |
| [04 Code review engineer](04_CODE_REVIEW_ENGINEER.md) | `code-review/` |
| [05 Security agent engineer](05_SECURITY_AGENT_ENGINEER.md) | `security-agents/` |
| [06 RL engineer](06_RL_ENGINEER.md) | `rl-defense/` |
| [07 Integration engineer](07_INTEGRATION_ENGINEER.md) | `monitoring/`, GitHub, cross-subsystem wiring |
| [08 Testing engineer](08_TESTING_ENGINEER.md) | `tests/`, evaluation |
| [09 Architecture reviewer](09_ARCHITECTURE_REVIEWER.md) | Reviewing designs and PRs |

Every prompt inherits the rules in [AGENTS.md](../../AGENTS.md); where they
differ, AGENTS.md wins and the prompt should be fixed.

- [10_STANDARDS_ALIGNMENT](10_STANDARDS_ALIGNMENT.md) — implementation prompt: ATT&CK, D3FEND, NIST SP 800-61, CVSS, CWE, OWASP LLM Top 10 (not yet implemented as of 2026-10-17).
