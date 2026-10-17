# MSG: Frontend app is live on `feat/vihaan/frontend`; browser e2e passes on the real stack

- From: vihaan
- To: all (action items for srihith, alan, adam, sarosh, sai)
- Kind: integration / evidence
- Timestamp (UTC): 2026-10-17T04:06:59Z
- Branch: `feat/vihaan/frontend` (PR linked in coordination/status/VIHAAN.md); issues #9, #29, #2, #38

## Summary (facts)

Next.js 16 + strict TS + Tailwind app in `frontend/`, every page backed by `/api/v1`
through `frontend/transport` (generated `shared/` schemas, AJV-validated): projects,
repos/snapshots, scopes (request / other-member approve / revoke), assessment live
timeline over durable SSE (+5 s polling fallback), eight agent lanes with provider mode
and tool trace, remediation approval gate, finding evidence chain, hash-checked diffs,
Verify checks, approvals inbox, monitoring feed, RL recommendations, Defense Lab.
`app/api/v1/[...path]` is a runtime same-origin proxy to `BACKEND_ORIGIN`.
Sai's Ari AI rebrand PRs (#43–#47, merged into this branch) are integrated and retested.

## Executed evidence (local, macOS, Node 24, Python 3.12, embedded PostgreSQL 16)

- `npm test --prefix frontend/transport`: **18 passed** (13 existing + 5 new for the added reads).
- `npm run lint`, `npm run typecheck`: clean. `npm test` (Vitest): **23 passed**. `next build`: ok.
- `tests/e2e/stack.py` (real FastAPI + migrations + worker + `next start` + Playwright,
  Chrome channel): **8 passed**. The journey test completes one assessment of
  `examples/payments-lite` entirely through the UI: reviewer + scout, probe, trace,
  diagnose, patch, verify, fortify all `succeeded`; Probe `confirmed`; Verify `accepted`
  5/5 checks; diff artifact SHA-256 matches the server header; state survives reload.
- Model replies are the backend's TEST-ONLY scripted transports; every run is persisted
  `provider_mode="fake"` and the UI shows "Not a live-provider run". No live provider call
  was made and none is claimed.
- Not run: `npm run test:integration --prefix frontend/transport` on this machine (the
  embedded pgserver cannot start from a repo path containing a space; CI is unaffected).

## Observed backend behaviour for owners (found by rendering real records)

1. **alan / srihith**: after a completed run the security finding stays
   `status=hypothesis` with an empty `history`, although its ValidationResult is
   `confirmed` and its patch has an `accepted` VerificationResult. The functional finding
   does reach `validated`. Expected: `validated → diagnosed → patch_proposed → verified`
   transitions with `StatusChange` entries. The UI shows the persisted status honestly.
2. **srihith**: `Assessment.usage.tool_calls` is 0 while the eight AgentRuns record 30
   tool calls in total (`llm_calls` does aggregate). `sandbox_seconds` is also 0.0.
3. **srihith (API asks, non-blocking)**: (a) `GET /projects/{id}/defense-recommendations`
   adds a top-level `label` beside `items/next_cursor`, unlike other list envelopes; the
   transport accepts it explicitly. (b) No snapshot list endpoint. (c) `GET /findings/{id}`
   and `/assessments/{id}/report` envelopes are not shared DTOs; the transport validates
   their parts. A `FindingDetail` DTO in `shared/` would remove that local mapping.
4. **adam**: the Defense Lab renders `defense_lab.json` as-is (validated against your
   schema server-side), shows `caveat` / `simulation_only` always and
   `hidden_stage_ground_truth` only in the replay, labelled "ground truth (simulation)".
   Nothing outside the bundle is plotted. Until a backend endpoint serves it the source
   path + SHA-256 are displayed.
5. **sarosh**: ACK #38 contracts as a consumer; the UI will add confirm/conflict/reject
   controls on expectations once `ExpectationDecision` routes exist. Transport extended in
   place (no breaking change to your exports).

## Asks

- srihith/alan: items 1–2 (finding status transitions, usage aggregation).
- srihith: review/merge the frontend PR; `frontend.yml` adds a Postgres-backed e2e job.
