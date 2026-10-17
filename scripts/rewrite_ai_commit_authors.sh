#!/usr/bin/env bash
# Rewrite commit/author identity so GitHub Contributors lists only the six humans.
# AI authors (Cursor Agent, Claude, cursor[bot]) become Adam Issac.
# Duplicate emails for Sai / Alan / Srihith / Sarosh / Vihaan / Adam are normalized.
#
# DANGEROUS: rewrites history. Requires a coordinated force-push of every shared
# branch (at least origin/main). Do not run unless the owner approved a rewrite.
#
# Usage (from a clean worktree of this repo):
#   ./scripts/rewrite_ai_commit_authors.sh
#   git push --force-with-lease origin main
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
cd "$root"

if [[ "${I_APPROVE_HISTORY_REWRITE:-}" != "yes" ]]; then
  echo "Refusing to rewrite history." >&2
  echo "Re-run with I_APPROVE_HISTORY_REWRITE=yes after the owner approves a force-push." >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Working tree is dirty; commit or stash first." >&2
  exit 1
fi

export FILTER_BRANCH_SQUELCH_WARNING=1
git filter-branch -f --env-filter '
canonical_adam_name="Adam Issac"
canonical_adam_email="62719255+adamissac@users.noreply.github.com"

rewrite() {
  local name="$1" email="$2"
  export GIT_AUTHOR_NAME="$name"
  export GIT_AUTHOR_EMAIL="$email"
  export GIT_COMMITTER_NAME="$name"
  export GIT_COMMITTER_EMAIL="$email"
}

ae="$GIT_AUTHOR_EMAIL"
an="$GIT_AUTHOR_NAME"
if [ "$ae" = "cursoragent@cursor.com" ] \
  || [ "$ae" = "206951365+cursor[bot]@users.noreply.github.com" ] \
  || [ "$ae" = "noreply@anthropic.com" ] \
  || [ "$ae" = "adamissac08@gmail.com" ] \
  || [ "$an" = "Cursor Agent" ] \
  || [ "$an" = "cursor[bot]" ] \
  || [ "$an" = "Claude" ]; then
  rewrite "$canonical_adam_name" "$canonical_adam_email"
elif [ "$ae" = "saisirichowdarapu@Saisiris-MacBook-Air.local" ] \
  || [ "$ae" = "saisirichowdarapu@Mac.attlocal.net" ]; then
  rewrite "Saicharan Chowdarapu" "137108827+SaiC123@users.noreply.github.com"
elif [ "$ae" = "fam.mozhoor@gmail.com" ] || [ "$an" = "m-alan08" ]; then
  rewrite "Alan Mozhoor" "alanmozhoor@gmail.com"
elif [ "$ae" = "saroshdoddaka334@gmail.com" ]; then
  rewrite "Sarosh Doddaka" "114310140+saroshdoddaka@users.noreply.github.com"
elif [ "$ae" = "vvihaankrishna@gmail.com" ]; then
  rewrite "Vihaan Krishna" "106044596+vihaankrishna100@users.noreply.github.com"
elif [ "$an" = "srihithys" ]; then
  rewrite "SrihithY" "srihithys@gmail.com"
fi
' --tag-name-filter cat -- --branches --tags

echo "Rewrite complete in this clone."
echo "Inspect with: git shortlog -sn"
echo "Then force-push shared branches (main first) with team coordination."
