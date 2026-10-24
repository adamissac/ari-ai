# Live Defense Phase 7A — first-responder engineering report

Status: **observed on `cursor/live-defense-first-responder-0044` from live `origin/main`**.
This is not customer-production evidence, not a claim that first-responder
prevented breaches, and not authorization to start Phase 7B or train RL.

**Verdict for one company-owned staging app: ENGINEERING GO FOR OWNED STAGING.**
Leave the PR open for human security review (authz / mode / privilege surface).

## Return fields

| Item | Status |
|---|---|
| PR | opened from `cursor/live-defense-first-responder-0044` (exact requested name was `feat/live-defense-first-responder`; Cloud Agent branch rule required `cursor/…-0044`) |
| Merge | **left open** for human security review (mode + privilege + trust-boundary expansion) |
| Modes | OFF / MONITOR\|SHADOW / ASSISTED RESPONSE; AUTO-EXECUTE rejected; fail closed |
| Seven agents | All seven in the capability registry from real `AgentSpec`s. Live dispatch is gated; Probe/Patch/Verify do not auto-run disruptively |
| e2e | Backend owned-test ingest → decision → handoff with provider ack; Playwright First responder tab 1 passed |
| RL data | Versioned `FirstResponderDecision` records; `predicted_probability` is always null; no training started |
| Codex / v6 | not trained, promoted, or edited |

## Live GitHub (do not trust stale handoffs)

Checked with live PR pages and `git fetch origin main` during this session.

| Fact | Observed |
|---|---|
| `origin/main` SHA | `a97820f1` (merge of PR #438, Adam status). Session started on `211c2b24` (PR #435); fast-forwarded before commit |
| PR [#411](https://github.com/adamissac/ari-ai/pull/411) | MERGED as `5d1e7b91` — Phase 6 CONDITIONAL GO |
| PR [#412](https://github.com/adamissac/ari-ai/pull/412) | **OPEN** — Phase 6.5 RL-gated pilot; SCHEMA_VERSION 0.20.0 on that branch. This PR also uses 0.20.0 from main; #412 must rebase to 0.21.0 if both land |
| PR [#422](https://github.com/adamissac/ari-ai/pull/422) | MERGED |
| PR [#430](https://github.com/adamissac/ari-ai/pull/430) | MERGED |
| PR [#433](https://github.com/adamissac/ari-ai/pull/433) | MERGED |
| PR [#435](https://github.com/adamissac/ari-ai/pull/435) | MERGED as `211c2b24` |
| PR [#438](https://github.com/adamissac/ari-ai/pull/438) | MERGED as `a97820f1` (docs/status only; not in the original checklist) |
| `SCHEMA_VERSION` | `0.20.0` additive |
| Alembic | `0015` |
| Codex / v6 / datasets | not trained, promoted, or edited |

## Architecture map (reuse, do not rebuild)

```
INGEST (existing)
  POST /ingest/runtime/{project}  → runtime_windows + MonitoringEvent
  job live_defense_shadow         → LivePolicyDecision { enforcement: NOT_EXECUTED }

FIRST RESPONDER (this phase; isolated job kinds)
  POST /projects/{id}/first-responder/mode   owner, audited
  job live_defense_first_responder           deterministic orchestrator 7a.1.0
      → FirstResponderDecision (versioned record, no invented probabilities)
      → FirstResponderInvocation (honest skip/queue; never fake success)
      → AnalystHandoff (delivered only after provider ack)
  job live_defense_agent_step                gated Scout/Trace/Diagnose/Fortify
                                             Probe iff AuthorizedScope
                                             Patch worktree-only, never deploy
                                             Verify independent of Patch

ENFORCEMENT (existing Phase 4; not started by first-responder)
  authorize.check → LiveControl → live_defense_execute
  OFF does not cancel these jobs or change their expiry/rollback/kill-switch
```

Unchanged: Codex research, v6 checkpoints, holdout, `rl-defense/` training.

## Control boundaries

- No AUTO-EXECUTE.
- OFF cancels first-responder jobs only. Independently authorized `LiveControl` jobs keep expiry, rollback, and kill-switch.
- Stop-monitoring (OFF) ≠ stop-enforcement (emergency stop). Kill-switch does not cancel first-responder monitoring.
- No silent retention-policy change.
- Probe: no external probes without AuthorizedScope.
- Patch: worktree only; silent customer deploy refused.
- Verify: independent of Patch.
- Untrusted telemetry is ignored. Secrets-like payloads stay quarantined on the ingest path.
- LLM prose is never proof of a confirmed threat.
- Org intent ≠ app effective permissions (disconnected app is effective OFF).

## Capabilities actually integrated

| Agent | In registry | Live first-responder path |
|---|---|---|
| Scout | yes (read-only tools, no network) | eligible when mapping+snapshot exist; otherwise `skipped_no_mapping` / `skipped_no_snapshot` |
| Trace | yes | blocked until confirmed Probe evidence exists |
| Diagnose | yes | same as Scout |
| Fortify | yes | same as Scout |
| Probe | yes (`target-only`) | ASSISTED + active AuthorizedScope; confirmation stays unverified without executed template evidence |
| Patch | yes (`worktree`) | ASSISTED + human remediation approval; never deploy |
| Verify | yes (independent sandbox) | ASSISTED + PatchCandidate; no Patch transcript |

All seven contracts are preserved. This is not a live Claude seven-agent run.

## Evidence executed

```
make check
  ruff pass; format 193 files; shared.export --check 154 files; examples check pass

uv run mypy
  Success: no issues found in 40 source files

uv run pytest -q backend/tests/test_live_defense_phase7a.py \
  backend/tests/test_parallel_migrations.py \
  backend/tests/test_live_defense_authorize.py \
  backend/tests/test_live_defense_phase5.py \
  backend/tests/test_live_defense_phase6.py
  43 passed

uv run pytest -q shared/tests/test_contracts.py backend/tests/test_live_defense_phase7a.py
  95 passed, 1 skipped (TSC unset)

npm run lint --prefix frontend && npm run typecheck --prefix frontend
  pass

npm test --prefix frontend
  330 passed / 78 files

npm test --prefix frontend/transport
  35 passed

cd frontend && E2E_BROWSER_CHANNEL=chrome ../.venv/bin/python tests/e2e/stack.py \
  tests/e2e/live-defense-phase7a.spec.ts
  1 passed (2.5s) — First responder tab, MONITOR mode, seven-agent registry, no AUTO-EXECUTE
```

Mode tests covered: default OFF; AUTO-EXECUTE 400/422; outsider 404; member 403;
SHADOW aliases MONITOR; disconnected app effective OFF; OFF cancels FR jobs and
leaves `live_defense_execute` queued; ingest in ASSISTED never enqueues execute;
handoff confirm 409 until executed Probe evidence (and `completed_unverified` is
still not confirmation); delivery-ack required for `delivered`.

Escalation demo: ASSISTED ingest opens an analyst handoff in `delivery_pending`
with `confirmation=unverified`; provider ack moves it to `delivered`.

## Limitations

- First-responder agent steps do not run a live Claude loop in this PR. Invocations are permission-gated and honestly skipped or marked `completed_unverified`. That is not fake confirmed-threat success.
- Frozen v6 is unchanged and still not executed defense.
- Correlation never claims HIGH; owner-attested mappings are MEDIUM or LOW.
- No customer production grants.
- Playbook AUTO-EXECUTE / Phase 7B are not started.

## Runtime readiness

Owned staging: first-responder can be switched MONITOR or ASSISTED on a connected
owned-test app. Shadow ingest still records `LivePolicyDecision` NOT_EXECUTED.
First-responder jobs are isolated. Independently authorized controls are
untouched by OFF.

Not ready: customer production, autonomous execution, live seven-agent Claude.

## RL-data readiness

Versioned `FirstResponderDecision` rows exist (`orchestrator_version=7a.1.0`,
`predicted_probability=null`, `executed=false`, `outcome_label` unset). Codex
may later consume them via `shared` contracts. **Do not train.** No invented
probabilities. Schema 0.20.0 collides with open #412 — rebase #412 to 0.21.0
if both land.

## Next milestone

Phase 7B is **not** started. Future RL may train against versioned
`FirstResponderDecision` records after Codex coordinates schema consumption and
a human security review merges this PR. Owner-only later authorization is
required before any company pilot beyond owned staging.
