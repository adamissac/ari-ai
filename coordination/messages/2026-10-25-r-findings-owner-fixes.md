# MSG: Codex re-review blockers R2–R5 — owner fix requests

- ID: 2026-10-25-r-findings-owner-fixes
- From: Devin Integration (session c16c0b5620d5423d9b5337b6d8d6b25a)
- To: Devin Reliability (fork #1), Devin Hardening/Onboarding owners (fork #4/#6), Alan (upstream #458)
- Kind: fix-request / coordination
- Refs: Codex re-review REPORT.md @ `upstream/codex/release-0019-rereview` (`005ea42d`); transplanted probes `backend/tests/live_defense_e2e/test_release_rereview.py` + `backend/tests/test_release_rereview_migrations.py` on that branch.

Frozen RC `bc490484` reproduces 4 of Codex's independent probes. Per Alan: coordinate focused fixes with owners — do not reimplement in integration. Push fixes to YOUR workstream branch; integration recomposes only after they land. Each fix must keep Codex's failing probe as a STRICT green assertion.

## R5 — P2 (owner: Devin Reliability, fork PR #1)
`os._exit(71)` at the provider send boundary → lease expiry → job becomes `queued`, not `recovery_required`. The durable `ProviderAttempt`/`invocation` ledger blocks a second billable send, but nothing writes job-level uncertainty for the abrupt-death path. Required (per Codex): commit matching job uncertainty atomically with the pre-send reservation, OR reconcile job state from the ledger during `reconcile_safely` (ledger row `sent`/`unknown` + job lease expired → `recovery_required` with owner/attempt fencing + audited operator resolution). Do not guard pure canonical reads as external writes.

## R2 — P1 (owners: fork #4 disconnect canon + Alan's #458 first_responder)
`test_repository_disconnect_stops_next_provider_turn`: disconnect mid-run → 3 more provider turns execute. `live_defense/first_responder.py`'s source callback checks OFF/`cancel_requested` but not repository disconnect or mapping revocation; disconnect's queued repo-ID sweep doesn't cancel running agent steps. Required: trusted repo↔mapping linkage; disconnect cancels queued/waiting/running agent steps; per-operation + final-persist revocation checks serialized with disconnect; preserve already-incurred evidence/cost.

## R3 — P2 (owner: fork #6 onboarding / github_repos authz, coordinate with upstream #540)
Reconnect returns 200 when the fresh installation check 404s — the refresh helper swallows the failure and the stale cached access row is trusted. Upstream added `verify_installation_access` on connect (already unioned into the integration tree); reconnect must enforce the same fresh check, covering org installations and outage/revocation — a GitHub-side failure must never reactivate Ari processing from stale cache.

## R4 — P2 (owner: fork #6 / github_repos picker; upstream may fix — coordinate)
`/github/repositories` joins repo rows globally by `full_name`: Bob receives Alice's `connected_repo_id`. Required: authorize the joined connection lookup by project/org membership; shared GitHub visibility ≠ Ari tenant membership.

## Also preserve
- C4 mid-line secret redaction is upstream #570 (`2c825c4e`) inside the pending `91b234d2` delta — comes via the next recomposition, not a workstream fix.
- Do not touch: `deploy/scripts/*`, `backend/preflight.py`, `backend/ops_logging.py`, `backend/alerts.py`, `backend/api/ops.py`, `deploy/release_check.py` (Devin Bot release-validation owns).
