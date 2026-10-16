# Claude Code, Codex and optional plugin/skill research (checked Oct 2026)

## Verified official documentation

- Anthropic Claude model IDs: `https://platform.claude.com/docs/en/models/overview` — currently lists **`claude-opus-5-5`**; runtime gateway should expose model env config and detect access errors.
- Anthropic Claude API SDK/skill: `https://platform.claude.com/docs/en/agents-and-tools/agent-skills/claude-api-skill` — the **Claude API** skill is bundled with current Claude Code; use it when wiring model calls; no special third-party install required.
- Claude Code project skills: `https://code.claude.com/docs/en/skills` — `.claude/skills/<name>/SKILL.md` with YAML frontmatter; descriptions control activation. Avoid bloated mandatory root prompt; activate skills per task.
- Claude Code custom subagents: `https://code.claude.com/docs/en/sub-agents` — `.claude/agents/*.md` can define development assistants with frontmatter (`name`, `description`, `tools`, `model`). **These are coding helpers**, separate from product runtime agents.
- Claude Marketplace: `https://claude.com/marketplace/plugins` — current listings include **Superpowers** (TDD/debugging), **Code Review**, **Context7**, **Frontend Design**, **Code Simplifier**. Availability and exact install commands can change; use the Claude Code `/plugin` marketplace UI and inspect permissions before installing.
- Codex skill format: `https://developers.openai.com/blog/skills-agents-sdk` and `https://developers.openai.com/blog/eval-skills` — repo-local skills under `.agents/skills/<name>/SKILL.md` with YAML metadata. Codex automatically reads `AGENTS.md` guidance.
- Codex engineering plans: `https://developers.openai.com/cookbook/articles/codex_exec_plans` — ExecPlans for multihour tasks; useful but not a substitute for code/tests.

## Recommended development enhancements (optional, install only as needed)

| Tool/skill | Why useful here | Priority | Install/verification strategy |
|---|---|---|---|
| Bundled `claude-api` | Correct Anthropic SDK tool-use, schema, usage and retries | Essential when implementing live agents | Already shipped with Claude Code; invoke `/claude-api` or request it as needed |
| **Superpowers** | Disciplined TDD, systematic debugging, planning for large features | High for all | Find by name in Claude Marketplace, read requested permissions before enabling |
| **Context7** | Current source docs for Python/FastAPI/Next.js/Gymnasium/PyTorch APIs | High if docs lookup needed | Install verified marketplace plugin with official source; do not treat outputs as authority for security decisions |
| **Code Review** | Secondary independent PR review and issues | Medium | Marketplace plugin, but actual project tests remain authoritative |
| **Frontend Design** | Better UX components/visual polish | Medium for Vihaan | Marketplace plugin if available; no replacement for e2e integration |
| **Code Simplifier** | Reduce complexity after feature tests pass | Low | Marketplace; require regression tests and review |
| GitHub CLI `gh` | Real issues/PR coordination, no extra AI plugin | Essential | Use account's existing auth/permissions; `gh auth status`; Git remote named `origin` |
| Playwright | Browser e2e, screenshot/testing actual API responses | High for Vihaan/Srihith | Add official Playwright dev deps/CLI to frontend, avoid relying only on UI screenshots |
| PyTorch/Gymnasium | Actual RL training and eval | Essential for Adam | Pin compatible versions and record hardware, dependencies and training seeds |

**Avoid** installing every plugin by default. More plugins increase tool overhead, permission footprint and prompt-injection surface. The pack itself contains repo-local, task-specific Claude/Codex skills and development subagents. It intentionally does not vend third-party plugin source code, imitate paid integrations, embed API keys, or claim installation in anyone's account.

## Agent teams vs GitHub coordination

Claude Code subagents/agent teams can help **within one session**, but each person's Claude Code session on a separate machine cannot directly share context through them. Use GitHub remote branches, PRs, issues and immutable message files as durable inter-person communication. Git pull/fetch is polling. Do not claim that agents are instantly aware of events or push branch conflicts away.

## Model economics and safety

`claude-opus-5-5` is the requested default runtime model; add per-agent overrides only with explicit config and logs. Each assessment must have token/USD and time budgets and opt-in live external API calls when configured. Real provider access may incur cost. The six coding assistants' model choices are governed by their Claude Code accounts, separate from product runtime gateway.
