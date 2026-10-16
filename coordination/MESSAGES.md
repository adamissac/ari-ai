# Shared team messages (index and mandatory read protocol)

This is the **single canonical team communication entry point**. Individual messages are **immutable** Markdown files in `coordination/messages/`, not concurrent edits to this index. This avoids overlapping Git writes from six coding agents.

**Everybody must check at session start, before modifying any shared interface, after each integration milestone, immediately before opening a PR, and before ending the session.** Fetch the current `origin/main`, inspect GitHub PRs/issues and any new messages on team branches. Agents do not have push notifications merely by reading this file; git fetch and PR review are necessary.

Each message file format: `YYYYMMDDTHHMMSSZ-<sender>-to-<recipient>-<slug>.md`. Example: `20261016T224000Z-sarosh-to-srihith-contextpack-schema.md`. Use UTC time, actual current value. Sender/recipient one of `adam,alan,sarosh,sai,vihaan,srihith,all`. Include fields as in [message template](templates/MESSAGE_TEMPLATE.md).

**Delivering a message:** Commit on your own branch, push, and create/update a PR. Because teammates don't automatically fetch your private branch, also post a GitHub issue/comment for time-sensitive requests, linking branch and file. Never assert a message is visible on `main` until merged. For a schema-blocking question that everyone needs right away, use a small coordination-only PR or GitHub issue and tag recipients.

**Replying:** Create a new file with `In-Reply-To:` containing original message path, rather than changing another person's file. Mark decision in `coordination/CONTRACTS.md` only via Srihith's contract PR or reviewed change.

**Required update cadence:** Every completed task, API/interface change, blocker, PR creation, and session end. Do not flood with tool logs. Make messages actionable: owner, expected output, schema, timeframe, commit/PR, and unblock action.

**Status:** Each person edits only `coordination/status/<name>.md` and adds their own session log entries. The team can view all six without merge conflicts.
