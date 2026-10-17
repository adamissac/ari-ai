# MSG: DECISION (repo owner) — merge your work into main every 30-60 minutes
- ID: `20261017T013517Z-adam-to-all-merge-to-main-often`
- From: adam (repo owner)
- To: all
- Kind: `decision`
- Timestamp (UTC): 2026-10-17T01:35:17Z
- Branch / commit / PR or issue link: committed directly to `main`; tracking issue in the next message line
- Related subsystem(s): all
- Summary (facts, not assumptions): Models can run out of usage mid-session, and work that sits only on a laptop or an unmerged branch is lost or invisible. **This decision overrides any instruction that says "never push to main" or "wait for approval before merging".**
- Interface requested/proposed: Mandatory for every developer and agent, starting now:
  1. Commit after every passing test or finished sub-step, at least every 30 minutes.
  2. Push after every commit.
  3. **Merge your branch into `main` at least every 30-60 minutes, after every milestone, and always before your session or model usage might end. Don't wait for permission.** Steps:
     ```
     git fetch origin && git merge origin/main          # bring main into your branch first
     <run your subsystem's tests>                        # never merge failing tests
     gh pr create --fill 2>/dev/null; gh pr merge --merge
     ```
  4. Keep PRs small and short-lived. Don't leave drafts open for hours: merge what passes and continue in a new PR.
  5. Never force-push `main`. If a merge conflicts in another owner's files, keep both sides, rerun the tests, and message that owner.
  6. Still required: fetch and read what changed (main, branches, PRs, issues, new messages) before every commit, push and merge.
- Breaking change? migration/test impact: Process only.
- Action required by recipient: Follow this from your next commit. Sarosh: PR #6 is still a draft. Please merge what passes now.
- Response-by milestone (not invented clock time): immediately.
- Evidence: `main` now contains PRs #1, #5, #7 and #8. Backend 40 passed / 1 skipped and rl-defense 63 passed on the merged tree.
- In-Reply-To (optional): `coordination/messages/20261017T003420Z-adam-to-all-git-cadence.md`
