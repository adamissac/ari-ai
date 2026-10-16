# 23 — Team onboarding

Status: **specified**. Team roster and owners: [planning/TEAM_ASSIGNMENTS](planning/TEAM_ASSIGNMENTS.md)
(all roles currently **UNASSIGNED**).

## Day 1 checklist

- [ ] Get access to the private repo `adamissac/hackatl-agentic-security`.
- [ ] Read [00 Start here](00_START_HERE.md) (everyone path, ~45 min).
- [ ] Read [15 Security boundaries](15_SECURITY_BOUNDARIES.md) — required before
      touching anything that runs code or sends traffic.
- [ ] Read [CONTRIBUTING](../CONTRIBUTING.md) and [24 Development standards](24_DEVELOPMENT_STANDARDS.md).
- [ ] Pick a role row in [TEAM_ASSIGNMENTS](planning/TEAM_ASSIGNMENTS.md) and agree it with the team.
- [ ] Install tools (below). There is nothing to build yet in Phase 0.
- [ ] Read the last entries of [SESSION_HANDOFF](planning/SESSION_HANDOFF.md).

## Tooling to install (for Phase 1)

| Tool | Version | Why |
|---|---|---|
| Git, GitHub CLI (`gh`) | recent | Repo, PRs |
| Python | 3.12 | Backend, agents, RL |
| `uv` (proposed) | recent | Python env + lockfiles (ADR pending, RQ-008) |
| Node.js | 20 LTS or newer LTS | Frontend |
| pnpm (proposed) | recent | Frontend package manager |
| Docker Desktop / Docker Engine | recent | Postgres, sandboxes |
| gitleaks | recent | Pre-commit secret scan |

Do **not** create cloud accounts or paid resources for the project without approval.

## Using coding agents on this repo

- Claude Code reads [CLAUDE.md](../CLAUDE.md) automatically; other agents should be
  pointed at [AGENTS.md](../AGENTS.md).
- Start each agent session with the relevant role prompt from
  [prompts/](prompts/README.md) and the task ID.
- Review agent output like any PR; agents must report commands actually run.
- Agents append to [SESSION_HANDOFF](planning/SESSION_HANDOFF.md) at the end of a session.

## How we work during the hackathon

- Daily (or per-block) 10-minute sync: done, next, blocked — against
  [HACKATL_TASKS](planning/HACKATL_TASKS.md).
- Integration checkpoints in [25](25_INTEGRATION_STRATEGY.md) are team events;
  whoever breaks a passed checkpoint fixes it first.
- Decisions with lasting consequences → ADR ([decisions/](decisions/README.md)).

## Who to ask

Roles in [TEAM_ASSIGNMENTS](planning/TEAM_ASSIGNMENTS.md). Until assigned, ask
in the team channel (channel name TBD).
