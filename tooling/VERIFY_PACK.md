# Installation and content verification

- Confirm `MASTER_BUILD_SPEC.md` present, 6 `team-prompts/*_IMPLEMENTATION.md`, 6 `start-messages/*_PASTE_IN_CLAUDE_CODE.txt`.
- Confirm exactly 8 `.claude/skills/*/SKILL.md` plus 8 `.agents/skills/*/SKILL.md`; 7 `.claude/agents/*.md` helpers.
- Run `python scripts/install_pack_instructions.py` in the cloned repo after extracting ZIP, then `git diff -- AGENTS.md CLAUDE.md` and review it.
- GitHub does **not** automatically extract uploaded ZIP files. A single blob upload is not enough for agents to see the Markdown; extract to repo tree with Claude Code or locally.
- Check `git status`, `git ls-files` after commit, then inspect new `coordination/messages/` messages and GitHub PRs regularly.
- Ensure each human works on a unique feature branch from a common base. Full product implementation cannot be inferred solely from the existence of this pack.
