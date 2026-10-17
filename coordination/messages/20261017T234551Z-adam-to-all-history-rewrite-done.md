# History rewrite applied — Contributors are the six humans only

**From:** Adam  
**To:** all  
**When:** now  

GitHub Contributors / commit authors no longer use Cursor, Claude, cursor[bot], or Devin.

What ran (owner-approved):
```bash
I_APPROVE_HISTORY_REWRITE=yes ./scripts/rewrite_ai_commit_authors.sh
git push --force-with-lease origin main
```

Rules used:
1. AI-authored commits → human **Co-authored-by** when present (e.g. Alan’s `amozhoor7`), else human committer, else Adam
2. Duplicate emails for Sai / Alan / Srihith / Sarosh / Vihaan / Adam → canonical identities
3. AI/Devin `Co-authored-by` trailers stripped

**New main tip:** `b120978` (was `ecb4d60`). Every SHA on `main` changed.

**What you must do locally (every clone / worktree):**
```bash
git fetch origin
git checkout main
git reset --hard origin/main
# Rebase or recreate any open feature branch onto the new main — do not merge old SHAs
```

Open PRs based on pre-rewrite commits need a rebase onto `origin/main`. Do not force-push other shared branches unless coordinated.
