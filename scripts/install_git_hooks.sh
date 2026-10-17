#!/usr/bin/env bash
# Install a pre-commit hook that blocks commits containing secrets (INFRA-003).
# Requires gitleaks on PATH (https://github.com/gitleaks/gitleaks). Idempotent.
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
hook="$root/.git/hooks/pre-commit"
cat > "$hook" <<'HOOK'
#!/usr/bin/env bash
# Installed by scripts/install_git_hooks.sh
if ! command -v gitleaks >/dev/null 2>&1; then
  echo "pre-commit: gitleaks not installed; skipping secret scan (CI still scans)." >&2
  exit 0
fi
exec gitleaks git --pre-commit --staged --no-banner --redact --config "$(git rev-parse --show-toplevel)/.gitleaks.toml"
HOOK
chmod +x "$hook"
echo "installed $hook"
