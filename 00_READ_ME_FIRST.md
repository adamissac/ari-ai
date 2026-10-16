# HackATL: six-developer production implementation pack

**Repository verified:** `https://github.com/adamissac/hackatl-agentic-security` (private; foundation documentation exists). This archive is an **overlay of new files**, not a replacement for the existing architecture. Extract its folders into the root of that repository, preserving paths. Existing `AGENTS.md`, `CLAUDE.md`, and `docs/` specifications are source-of-truth. Do not overwrite them with older templates.

## What is inside

- `MASTER_BUILD_SPEC.md`: shared, executable product requirements and completion criteria.
- `team-prompts/`: six detailed implementation mandates, one per developer.
- `START_MESSAGES.md`: copy/paste first messages for all six Claude Code sessions.
- `coordination/`: async communication protocol, message index, interface rules, milestones and templates.
- `.claude/agents/`: project-level *development* subagents; **not** the seven *product runtime* agents.
- `.claude/skills/`, `.agents/skills/`: parallel Claude Code and Codex skills teaching the same workflows.
- `tooling/RESEARCH_AND_INSTALL.md`: researched tooling, official references, and installation guidance.
- `scripts/install_pack_instructions.py`: idempotently append references to existing root `AGENTS.md` and `CLAUDE.md` and check files.

## Initial install

1. Extract this archive into the root of `hackatl-agentic-security` **or commit the archive itself and have Claude Code extract it**. GitHub does **not** unpack ZIPs automatically.
2. Run `python scripts/install_pack_instructions.py` from the repo root (only appends a small section; leaves existing specs intact).
3. Commit/push this documentation overlay to `main` once, before starting six branches. Give every teammate the same base SHA.
4. Every person uses their text in `START_MESSAGES.md` and works on their **own feature branch**, not directly on `main`.
5. The team uses GitHub PRs/issues and `coordination/messages/` for asynchronous communication. Agents cannot literally watch GitHub continuously unless a process remains running; they check before milestones, before changes to shared interfaces, before PRs, and after pulling updates.

## Important

This pack **does not implement the product**. It instructs the six coding agents to implement it and provides repeatable acceptance tests. Completion requires execution, real model/tool loops, training and evaluation, integration, and evidence. A single coding session may not finish everything: on resource/time limits, commit tested progress and record exact blockers, then resume.

Team participants have indicated permission for repository-level implementation within their approved workspace, but **do not** interpret that as permission to access arbitrary systems, launch attacks against external targets, purchase services, reveal secrets, disable safeguards, or make destructive changes to other users' resources. Operational safety gates and provider permissions remain in force.

No historical/rebuild narrative is included anywhere in the pack.
