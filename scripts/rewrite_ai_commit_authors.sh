#!/usr/bin/env bash
# Rewrite commit identity so GitHub Contributors lists only the six humans.
#
# For AI-authored commits (Cursor Agent, Claude, cursor[bot]):
#   1. Prefer the first human Co-authored-by trailer
#   2. Else prefer a human committer
#   3. Else fall back to Adam Issac
# Also normalizes duplicate emails for Sai / Alan / Srihith / Sarosh / Vihaan / Adam,
# and strips AI / Devin Co-authored-by trailers from commit messages (those still
# create GitHub contributor rows).
#
# DANGEROUS: rewrites history. Requires a coordinated force-push of every shared
# branch (at least origin/main). Do not run unless the owner approved a rewrite.
#
# Usage (from a clean worktree of this repo):
#   I_APPROVE_HISTORY_REWRITE=yes ./scripts/rewrite_ai_commit_authors.sh
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

git filter-branch -f \
  --env-filter '
canonical_adam_name="Adam Issac"
canonical_adam_email="62719255+adamissac@users.noreply.github.com"
canonical_sai_name="Saicharan Chowdarapu"
canonical_sai_email="137108827+SaiC123@users.noreply.github.com"
canonical_alan_name="Alan Mozhoor"
canonical_alan_email="alanmozhoor@gmail.com"
canonical_srihith_name="SrihithY"
canonical_srihith_email="srihithys@gmail.com"
canonical_sarosh_name="Sarosh Doddaka"
canonical_sarosh_email="114310140+saroshdoddaka@users.noreply.github.com"
canonical_vihaan_name="Vihaan Krishna"
canonical_vihaan_email="106044596+vihaankrishna100@users.noreply.github.com"

is_ai_email() {
  case "$1" in
    cursoragent@cursor.com|noreply@anthropic.com|206951365+cursor[bot]@users.noreply.github.com|158243242+devin-ai-integration[bot]@users.noreply.github.com) return 0 ;;
    *devin-ai-integration*) return 0 ;;
  esac
  return 1
}

is_ai_name() {
  case "$1" in
    "Cursor Agent"|"cursor[bot]"|Claude|"Claude Opus 5.5"|Cursor|"Devin AI"|"devin-ai-integration[bot]") return 0 ;;
  esac
  return 1
}

canon_human() {
  local email="$1" name="$2"
  if is_ai_email "$email" || is_ai_name "$name"; then
    return 0
  fi
  case "$email" in
    62719255+adamissac@users.noreply.github.com|adamissac08@gmail.com)
      printf "%s|%s\n" "$canonical_adam_name" "$canonical_adam_email"; return 0 ;;
    137108827+SaiC123@users.noreply.github.com|saisirichowdarapu@Saisiris-MacBook-Air.local|saisirichowdarapu@Mac.attlocal.net)
      printf "%s|%s\n" "$canonical_sai_name" "$canonical_sai_email"; return 0 ;;
    alanmozhoor@gmail.com|fam.mozhoor@gmail.com|amozhoor7@gatech.edu)
      printf "%s|%s\n" "$canonical_alan_name" "$canonical_alan_email"; return 0 ;;
    srihithys@gmail.com)
      printf "%s|%s\n" "$canonical_srihith_name" "$canonical_srihith_email"; return 0 ;;
    saroshdoddaka334@gmail.com|114310140+saroshdoddaka@users.noreply.github.com)
      printf "%s|%s\n" "$canonical_sarosh_name" "$canonical_sarosh_email"; return 0 ;;
    vvihaankrishna@gmail.com|106044596+vihaankrishna100@users.noreply.github.com)
      printf "%s|%s\n" "$canonical_vihaan_name" "$canonical_vihaan_email"; return 0 ;;
  esac
  case "$name" in
    m-alan08|amozhoor7|"Alan Mozhoor")
      printf "%s|%s\n" "$canonical_alan_name" "$canonical_alan_email"; return 0 ;;
    srihithys|"SrihithY")
      printf "%s|%s\n" "$canonical_srihith_name" "$canonical_srihith_email"; return 0 ;;
    "Adam Issac")
      printf "%s|%s\n" "$canonical_adam_name" "$canonical_adam_email"; return 0 ;;
    "Saicharan Chowdarapu"|"Saisiri Chowdarapu")
      printf "%s|%s\n" "$canonical_sai_name" "$canonical_sai_email"; return 0 ;;
    "Sarosh Doddaka")
      printf "%s|%s\n" "$canonical_sarosh_name" "$canonical_sarosh_email"; return 0 ;;
    "Vihaan Krishna")
      printf "%s|%s\n" "$canonical_vihaan_name" "$canonical_vihaan_email"; return 0 ;;
  esac
}

rewrite_to() {
  export GIT_AUTHOR_NAME="$1"
  export GIT_AUTHOR_EMAIL="$2"
  export GIT_COMMITTER_NAME="$1"
  export GIT_COMMITTER_EMAIL="$2"
}

ae="$GIT_AUTHOR_EMAIL"
an="$GIT_AUTHOR_NAME"
ce="$GIT_COMMITTER_EMAIL"
cn="$GIT_COMMITTER_NAME"

if is_ai_email "$ae" || is_ai_name "$an"; then
  chosen=""
  msg="$(git cat-file commit "$GIT_COMMIT" 2>/dev/null | sed "1,/^$/d" || true)"
  while IFS= read -r line; do
    case "$line" in
      [Cc][Oo]-[Aa][Uu][Tt][Hh][Oo][Rr][Ee][Dd]-[Bb][Yy]:*)
        rest="${line#*: }"
        rest="${rest# }"
        cname="${rest%%<*}"
        cname="${cname%"${cname##*[![:space:]]}"}"
        cemail="${rest##*<}"
        cemail="${cemail%>}"
        mapped="$(canon_human "$cemail" "$cname" || true)"
        if [ -n "${mapped:-}" ]; then
          chosen="$mapped"
          break
        fi
        ;;
    esac
  done <<< "$msg"
  if [ -z "${chosen:-}" ] && ! is_ai_email "$ce" && ! is_ai_name "$cn"; then
    chosen="$(canon_human "$ce" "$cn" || true)"
  fi
  if [ -z "${chosen:-}" ]; then
    chosen="$canonical_adam_name|$canonical_adam_email"
  fi
  rewrite_to "${chosen%%|*}" "${chosen##*|}"
else
  mapped="$(canon_human "$ae" "$an" || true)"
  if [ -n "${mapped:-}" ]; then
    export GIT_AUTHOR_NAME="${mapped%%|*}"
    export GIT_AUTHOR_EMAIL="${mapped##*|}"
  fi
  mapped_c="$(canon_human "$ce" "$cn" || true)"
  if [ -n "${mapped_c:-}" ]; then
    export GIT_COMMITTER_NAME="${mapped_c%%|*}"
    export GIT_COMMITTER_EMAIL="${mapped_c##*|}"
  fi
fi
' \
  --msg-filter "python3 \"$root/scripts/_rewrite_commit_msg_filter.py\"" \
  --tag-name-filter cat \
  -- --branches --tags

echo "Rewrite complete in this clone."
echo "Inspect with: git log --no-mailmap --format='%an <%ae>' | sort | uniq -c | sort -rn"
echo "Expect only the six canonical humans."
echo "Then force-push shared branches (main first) with team coordination:"
echo "  git push --force-with-lease origin main"
