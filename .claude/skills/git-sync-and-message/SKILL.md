---
name: git-sync-and-message
description: Synchronize repo and coordinate changes across six concurrent GitHub branches. Use when starting sessions, hitting milestones, changing interfaces, opening PRs or handing off.
---

# git-sync-and-message


0. Cadence: commit after every passing test or finished sub-step (at least every 30 minutes) and push after every commit. Run the full read-what-changed sequence from "Git cadence" in `AGENTS.md` before every commit, push, interface change and PR.
1. `git status --short`; identify owner branch and uncommitted changes. Do not overwrite, reset or discard someone else's work.
2. `git fetch origin`; inspect `origin/main` recent commits, own branch divergence, `gh pr list`, `gh issue list` and relevant comments if GitHub CLI available.
3. Read `coordination/MESSAGES.md`, new message files in `coordination/messages/`, `coordination/STATUS.md`, `coordination/CONTRACTS.md`, and six per-owner statuses. A PR branch file is not visible to peers until pushed and linked; issue/comment for urgent blockers.
4. For contract changes, produce exact schema/examples and dependencies; publish one immutable message file using the provided naming/template, not an edit to a global running chat log.
5. Push owned branch and open/update PR. Check checks, changed files and whether main drifted. Merge/rebase only with clean tree and appropriate reviews. Never force-push shared/protected branch.
6. On completion, leave `coordination/status/<PERSON>.md` with commit/PR, executed tests, unresolved blockers and next owner action. No invented remote status.
