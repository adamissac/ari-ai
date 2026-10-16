# 20 — HackATL demo script

Status: **specified (draft)**. Depends on [planning/MVP_SCOPE](planning/MVP_SCOPE.md).
Target length: **5 minutes** live + 2 minutes Q&A buffer (event format
unconfirmed — RQ-011).

## Ground rules

1. Everything shown is real output from the platform on our own deliberately
   vulnerable target `examples/payments-lite` (planned, `DEMO-001`).
2. Pre-recorded runs may be replayed for time, with the on-screen banner
   "Replay of recorded run <id>". Never fabricate output.
3. RL results are shown with the simulation caveat and the baseline table from
   [17](17_RL_EVALUATION_PROTOCOL.md).
4. No third-party systems, no real customer code.

## Demo target: `payments-lite` (planned)

A small FastAPI service with customers, payments and refunds, and seeded
fixture users. It contains, deliberately and documented in its README:
- **Functional bug:** refunds can exceed the original payment amount (violates
  an invariant stated in its docstring/tests).
- **Authorization weakness:** a payment-detail endpoint lacks the ownership check
  its sibling endpoints have (violates "a customer can only read their own
  payments").
- A test suite that passes on the buggy code (the gaps are untested).

## Storyline

| Time | Beat | On screen |
|---|---|---|
| 0:00 | Problem: tools don't know intent, don't prove, don't stay | One slide |
| 0:30 | Connect repo; show scope approval ("only the sandbox build of this repo") | Scope screen |
| 1:00 | Assessment starts; timeline lanes light up | Live timeline |
| 1:30 | Expectations discovered, incl. ownership rule with provenance | Expectations page |
| 2:00 | Functional finding: failing generated test for refund invariant | Finding detail |
| 2:30 | Security: Scout hypothesis → Probe validated (cross-user access check result) → Trace path | Evidence chain |
| 3:15 | Approve remediation → Patch diff → Verify: 5 checks pass in fresh sandbox | Patch + verification |
| 3:50 | Push a commit that reintroduces the bug → monitoring flags it → regression test fails | Monitoring feed |
| 4:20 | RL panel: recommendation + baseline comparison table + caveat | Monitoring panel / slide |
| 4:45 | Close: one intelligence layer, evidence for every claim | Slide |

## Backup plan

- Recorded run of the entire flow (screen capture) ready offline.
- Local stack pre-warmed; Docker images pulled; LLM responses recorded for replay
  if the network fails (banner shown).
- One teammate runs the demo, one narrates, one watches logs.

## Rehearsal checklist (`DEMO-002`)

- [ ] Full run from clean DB under 10 minutes; replay tested
- [ ] Budget meter shows real usage
- [ ] Every number on slides traceable to a run ID or eval summary
- [ ] Scope approval step shown, not skipped
- [ ] Laptop offline fallback tested
