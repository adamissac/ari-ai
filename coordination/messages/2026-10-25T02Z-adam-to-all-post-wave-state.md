# Post-merge-wave state — main green, two live-defense PRs remain (2026-10-25T02Z, adam/release-gate)

Main head `0f311913` — **20/20 checks green** (incl. gitleaks, intel-tests, e2e, inventory-lite).
Landed this wave: #530 (release gate), #571 (gitleaks allowlist), #572 (cross-org jobs test),
#570 (redaction gaps), #540, #538, #536, #532.

## Verified on main
- `redact_text` now scrubs `postgresql+psycopg://user:pass@` driver DSNs and
  `access_token=`/`DB_PASSWORD=`/`client_secret:` kv forms (commander findings 1+2 — spot-checked live).
- Cross-org jobs-list isolation regression is on main via #572.
- Alembic single head `0017` unchanged by this wave; no migration drift.
- 8/8 `test_redact_text_gaps.py` + 13/13 `test_privacy_redact.py` pass on main.

## #458 (feat/alan/live-defense-phase7c-agent-execution) — blocked, owner action needed
Merge conflicts: `CHANGELOG.md`, `docs/planning/SESSION_HANDOFF.md` (append-only, keep-both),
`backend/tests/test_sandbox_target.py` (main's method/body expansion vs branch's),
`shared/shared/__init__.py` — **schema-version collision**: main claimed `0.22.0` for
ops-readiness (#540); the branch's 7C bump is also `0.22.0`. Resolution: keep main's 0.22
comment, renumber the 7C schema to `0.23.0`, regenerate `shared/generated/`, update the
PR's version references. This PR is already flagged "do not merge — independent security
re-review requested", so the renumber is owner-lane work, not gate work.

## #412 (feat/live-defense-phase6-5-rl-gated-pilot) — blocked
Only conflict is `CHANGELOG.md` (trivial keep-both); PR is marked RL BLOCKED anyway —
low value to refresh until the RL blocker resolves.

## Still needs Adam (unchanged)
1. Branch protection on `main` — required checks list in docs/release/RELEASE_GATE_2026-10-24.md.
2. Hosted URL + ANTHROPIC_API_KEY to run `pilot-verify.yml` live-model + hosted-smoke legs
   on the final SHA (commands in the release doc).
3. Merge sign-offs on whatever remains.
