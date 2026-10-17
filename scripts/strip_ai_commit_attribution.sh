#!/usr/bin/env bash
# commit-msg hook: drop AI agent trailers; keep human Co-authored-by lines.
# Installed by scripts/install_git_hooks.sh
set -euo pipefail
msg_file="${1:?commit message file}"
tmp="$(mktemp)"
# Case-insensitive strip of Cursor / Claude / Codex / Anthropic agent trailers.
grep -viE \
  -e '^[[:space:]]*co-authored-by:[[:space:]]*cursor([[:space:]]|<)' \
  -e '^[[:space:]]*co-authored-by:[[:space:]]*cursor agent[[:space:]]*<' \
  -e '^[[:space:]]*co-authored-by:[[:space:]]*claude' \
  -e '^[[:space:]]*co-authored-by:[[:space:]]*codex' \
  -e '^[[:space:]]*co-authored-by:[[:space:]]*devin' \
  -e '^[[:space:]]*co-authored-by:.*noreply@anthropic\.com' \
  -e '^[[:space:]]*co-authored-by:.*cursoragent@cursor\.com' \
  -e '^[[:space:]]*co-authored-by:.*devin-ai-integration' \
  -e '^[[:space:]]*made-with:[[:space:]]*cursor' \
  -e '^[[:space:]]*made with cursor' \
  -e '^[[:space:]]*🤖[[:space:]]*generated with' \
  "$msg_file" >"$tmp" || true
# Trim trailing blank lines left after stripping.
perl -0pi -e 's/\n+\z/\n/' "$tmp" 2>/dev/null || true
mv "$tmp" "$msg_file"
