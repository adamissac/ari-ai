# Adam — implementation status

Owner: Adam
Branch: `feat/adam/release-gate` → PR #530 (open, awaiting human merge approval)
Last sync: 2026-10-24 ~22:40Z — origin/main at `466df4b7` (#534 merged); branch rebased/squashed onto it.

## In flight — release gate (PR #530)
- Always-on jobs + `scripts/ci/path_gate.py` (RUN/SKIP visible verdicts); unique job ids for required checks.
- `pilot-verify.yml` manual 7-category release pipeline.
- `GET /projects/{id}/jobs?status=` dead-letter visibility; `last_error` secret-scrubbed at **write time** (`redact()` in `jobs.fail` + lease-expired write); read side role-split: owners sanitized detail, members `{code, category}`.
- Eval harness: `scored:false` + `unscored_reason`; `summarize()` over scored cases only; case validation.
- `scripts/ci/load_probe.py` queue probe — all invariants green (~1.5k jobs/s embedded PG).
- Report + required-check list + admin runbook + trigger commands: `docs/release/RELEASE_GATE_2026-10-24.md`.
- Local evidence: 15 backend tests pass; ruff clean. CI re-running on latest head.

## Coordination in progress
- **Migration collision**: #533 (`0016_worker_heartbeats`) vs #535 (`0016_tenant_rls_intelligence`) — both claim revision `0016`. Order agreed: **#535 first** (tenant RLS gates private-code indexing); #533 renumbers to `0017` + updates head test. Comments posted on both.
- #531 (intel redaction/pipeline audit): resolved its merge conflict myself (CHANGELOG + SESSION_HANDOFF append conflicts); comment posted. Ready for its CI re-run.
- #524/#525/#526/#523 (ari-security authz fixes): merge cleanly alongside #530.
- #529: merges after #530 per the eval session — resolution is module-level `_finding_paths` + my scored/unscored fields.

## Blockers (require Adam/repo admin)
- `main` branch protection unset — exact settings + `gh api` command in the release doc.
- GitHub App installation token / hosted pilot URL / Anthropic key needed only for live-model + hosted-smoke gates (opt-in by design).

## Next actions
1. Wait #530 CI green → leave for merge approval (no merge by agents).
2. Track #533/#535 migration renumber on rebase.
3. Re-run `pilot-verify.yml` on the true final `main` SHA once merges settle.
