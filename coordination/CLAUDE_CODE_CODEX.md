# Claude Code and Codex coordination

## Owner instruction — November 5, 2026

Adam appointed Claude Code as the lead for the Ari pull-request cleanup. Claude Code is the boss for task assignment, technical direction, priorities, and merge sequencing. Codex will follow Claude Code's instructions within Adam's authorized scope and the repository's security, privacy, attribution, and branch-protection requirements. Adam's direct instructions remain authoritative.

## Communication

Use [issue #559](https://github.com/adamissac/ari-ai/issues/559) for live messages. Prefix each message with CLAIMED, WORKING, NEEDS_COORDINATION, BLOCKED, READY_FOR_REVIEW, MERGED, or DONE. Claude Code should post its current branch, claimed paths, exact next task, and any merge holds there. Codex must read new replies before editing overlapping paths and before each merge. A posted request is not an acknowledgment.

This file is the shared entrypoint and durable agreement, not a concurrently edited chat log. Use immutable files under coordination/messages/ for decisions and separate coordination/status/agents/<agent>.json records for agent state. Follow coordination/PROTOCOL.md; do not hand-edit the generated AGENT_BOARD.md.

## Cleanup scope

Inspect every open PR; fix actual conflicts, review findings, and failing checks; merge necessary changes once verified. Preserve useful work when closing duplicates or superseded branches, and link the replacement. Do not bypass protections or security gates. Keep commit messages and PR descriptions free of attribution trailers and generated-session footers.

Initial November 5 inventory: fifteen open PRs, including twelve repeated cloud-health reports, UI PR #818, and old live-defense PRs #412 and #458. Current remote state and new messages take precedence over this snapshot.

## Initial handoff to Claude Code

Codex has requested your current assignments on issue #559. The original local checkout is preserved; cleanup uses an isolated worktree and feat/adam/pr-cleanup-20261105. Railway production was online with zero reported issues at inspection; documentation-only Vercel builds were canceled and require distinguishing from the active production deployment.
