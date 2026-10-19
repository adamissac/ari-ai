# Contributors rewrite again — only the six humans on main

**From:** Adam  
**To:** all  
**When:** now  

GitHub commit authors on `main` had Claude again from merged #336 status no-op (`Claude <noreply@anthropic.com>` on `7c59e0b` / `35da8f0`). Mailmap cannot fix the Contributors graph.

What ran (owner-requested standing rule: human-only Contributors):
```bash
# fresh main-only clone
I_APPROVE_HISTORY_REWRITE=yes ./scripts/rewrite_ai_commit_authors.sh
git push --force-with-lease origin main
```

Rules (unchanged):
1. AI-authored commits → human **Co-authored-by** when present, else human committer, else Adam
2. Duplicate emails for Sai / Alan / Srihith / Sarosh / Vihaan / Adam → canonical identities
3. AI/Devin `Co-authored-by` trailers stripped

**New main tip:** `16cd462` (was `a5e0309`). Tree unchanged; every SHA on `main` changed again.

Authors on `main` now (only these six):
- Adam Issac
- SrihithY
- Saicharan Chowdarapu
- Alan Mozhoor
- Vihaan Krishna
- Sarosh Doddaka

**What you must do locally (every clone / worktree):**
```bash
git fetch origin
git checkout main
git reset --hard origin/main
# Rebase or recreate any open feature branch onto the new main — do not merge old SHAs
```

Open PRs need a rebase onto `origin/main`. Going forward: never land commits whose author is Claude/Cursor — set the human author (or human Co-authored-by) before merge. Cloud/status no-ops must use Adam’s identity, not the agent’s.
