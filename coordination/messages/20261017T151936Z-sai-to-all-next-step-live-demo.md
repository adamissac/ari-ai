# MSG: Next big step: one real, recorded live end-to-end demo run (owners needed)
- ID: `20261017T151936Z-sai-to-all-next-step-live-demo`
- From: sai
- To: all (alan, srihith, adam, sarosh, vihaan)
- Kind: `planning`
- Timestamp (UTC): 2026-10-17T15:19:36Z
- Branch / commit / PR or issue link: main @ 395fb1d; coordination/MILESTONES.md; docs/20_DEMO_SCRIPT.md
- Related subsystem(s): security-agents (live provider), backend, frontend, demo
- Summary (facts, not assumptions):
  - M0–M2 and M4–M7 are checked. **M3 is not**: the only live seven-role run (Srihith, 13:57Z, $0.38) got live Scout and Probe turns, but Probe returned *inconclusive* on the planted IDOR (`GET /payments/{payment_id}`, CWE-639). Trace, Diagnose, Patch, Verify and Fortify never ran.
  - Every end-to-end proof (M7, e2e) uses scripted model transports (`provider_mode=fake`). There is **no live-model run of the full storyline yet**, and none of the `docs/20_DEMO_SCRIPT.md` rehearsal checklist (DEMO-002) is ticked.
  - The UI and landing page are in demo shape. The biggest remaining risk is a judge asking "is this real?".
- Proposed plan and owners (someone needs to pick up each item):
  1. **Alan:** diagnose and fix Probe's inconclusive result. Add Probe's tool calls (name, input, result summary) to the CLI `--report`, and check the live-chosen `access_control.ownership` parameters against payments-lite. Zero cost; fake-provider tests.
  2. **Srihith (key holder), after explicit owner approval of the spend:** re-run once: `cd security-agents && RUN_LIVE_LLM_EVAL=1 LIVE_SEVEN_MAX_USD=8 ../.venv/bin/python -m pytest -q -m live tests/test_live_provider.py -k seven_roles -s`. Check M3 if all seven roles show live turns.
  3. **Volunteer (Srihith or Adam):** run the full storyline live through the UI on payments-lite:
     - connect the repo and approve the scope;
     - refund bug reproduced and IDOR validated;
     - approve remediation, Patch, independent Verify;
     - a reintroducing commit flagged by monitoring.

     Screen-record it as the required backup ("Replay of recorded run <id>").
  4. **Everyone:** the DEMO-002 rehearsal checklist: a clean run under 10 minutes, every slide number traceable to a run ID, an offline fallback, and who drives and who narrates.
  - Defer **M8** (deployment). It needs paid infrastructure and the demo doesn't need it.
- Breaking change? migration/test impact: None.
- Action required by recipient: reply with an immutable message claiming an item. Live spend needs the owner's explicit approval; no agent spends without it.
- Evidence: MILESTONES.md (M3 section and Srihith's live attempt), `20261017T135740Z-srihith-to-alan-live-seven-role-result.md`.
