# scripts/

> **What exists:** `check_links.py` and `install_git_hooks.sh` (INFRA-003).

## Purpose
Developer tooling only — never product logic.

## Planned scripts
| Script | Purpose | Task |
|---|---|---|
| `check_links.py` ✅ | Verify internal Markdown links, anchors and Mermaid block types (used by `docs.yml`) | INFRA-003 |
| `install_git_hooks.sh` ✅ | Install a gitleaks pre-commit hook that blocks staged secrets | INFRA-003 |
| `codegen_contracts.sh` | Pydantic → JSON Schema → TS into `shared/generated/` | CORE-003 |
| `dev_up.sh` / `dev_down.sh` | Wrap Docker Compose for the local stack | INFRA-004 |
| `build_sandbox_images.sh` | Build pinned `test-runner` / `check-runner` images | INFRA-005 |
| `replay_webhook.py` | Send recorded GitHub webhook fixtures to the local API with a valid signature | MON-001 |
| `seed_demo.py` | Seed a local DB with the demo project and scope request | DEMO-001 |
| `usage_report.sql` | LLM cost and token queries | [docs/19](../docs/19_OBSERVABILITY_AND_COST_CONTROL.md) |

## Rules
- Scripts are idempotent and print what they did.
- No secrets in scripts; read from environment.
- Nothing here contacts systems other than local services, GitHub (for the
  connected repo) and package registries.

## Interfaces
Command-line only. Documented commands are mirrored in [CLAUDE.md](../CLAUDE.md).

## Dependencies
Python 3.12 standard library preferred; Bash for thin wrappers.

## Commands
```bash
python3 scripts/check_links.py     # exit 1 on broken links/anchors
bash scripts/install_git_hooks.sh  # optional: block secrets before they are committed
```
