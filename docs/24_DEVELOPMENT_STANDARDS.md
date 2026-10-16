# 24 — Development standards

Status: **specified** for Phase 1 onward. Summary lives in
[AGENTS.md](../AGENTS.md) §9; this is the full version.

## Python

- Python 3.12; type hints on all public functions; `mypy --strict` target
  (per-package opt-in as packages mature).
- `ruff` for lint + format (line length 100, matching `.editorconfig`).
- `pytest`; tests next to the package in `<package>/tests/`.
- Pydantic v2 for every model crossing a boundary; `extra="forbid"` on inputs.
- No bare `except:`; no `except Exception: pass`. Map errors to the error-code
  catalog ([12](12_DATA_MODELS_AND_CONTRACTS.md)).
- Async FastAPI handlers; blocking work goes to the job queue, not request handlers.
- Each package exposes a public `api.py`; everything else is internal.

## TypeScript

- `strict: true`, ESLint (Next.js config + `@typescript-eslint`), Prettier.
- No `any` in exported types; API types imported from generated `shared/generated/ts`.
- Components: function components, colocated tests with Vitest + Testing Library (proposed).

## Dependency direction

```
frontend → (HTTP) → backend → shared
backend → code-intelligence(api) , monitoring(api)
worker  → code-intelligence, code-review, security-agents, rl-defense → shared
security-agents → code-intelligence(api) (retrieval only)
code-review → code-intelligence(api), security-agents(sandbox + tool registry api)
monitoring → code-intelligence(api)
shared → (nothing in repo)
```
Cycles are review-blocking. Enforced later with `import-linter` (proposed).

## Safety-critical code

Scope guard, approval checks, budget checks, sandbox configuration, tool
allowlists, Verify's verdict rules:
- deterministic, no LLM in the decision;
- 95% branch coverage target;
- two reviewers including the security owner;
- changes listed in the PR description under "Safety-critical changes".

## LLM prompts

- Prompts live as versioned files in the owning package (`prompts/<agent>/vN.md`),
  not inline strings scattered in code.
- Each prompt change bumps the version recorded in `AgentRun`.
- Output must be structured (tool/JSON schema) and validated.

## Review checklist

- [ ] Matches the task scope and spec; divergences have an ADR or spec update
- [ ] Contracts from `shared/`; no duplicates
- [ ] Tests meaningful and passing; SB suite unaffected or extended
- [ ] Security boundaries respected ([15](15_SECURITY_BOUNDARIES.md))
- [ ] Shared-context rules respected ([11](11_SHARED_CONTEXT_AND_MEMORY.md) §What would break)
- [ ] No secrets, no customer data, no third-party exploit details
- [ ] Errors use catalog codes; logs redacted
- [ ] Docs/README "What exists" updated; claims match code
- [ ] Commit messages Conventional Commits, no attribution trailers

## Documentation standards

- Every doc states its status (implemented/specified/proposed) near the top.
- Relative links only for internal docs; link checker in CI (`INFRA-003`).
- Diagrams in Mermaid inside Markdown.
- Each subsystem README has sections: Purpose, Responsibilities, Interfaces,
  Dependencies, What exists, Planned layout, Commands.

## Git

Branches, commits and PR rules: [CONTRIBUTING](../CONTRIBUTING.md) and
[AGENTS.md](../AGENTS.md) §13.
