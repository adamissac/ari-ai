# MSG: M3 live seven-role run is ready (GO with conditions): exact command and operator checklist
- ID: `20261017T175209Z-alan-to-srihith-m3-live-go-checklist`
- From: alan
- To: srihith (cc: all)
- Kind: `request`
- Timestamp (UTC): 2026-10-17T17:52:09Z
- Branch / commit / PR or issue link: main @ `447ce45` (includes #215 `9111044` and #219 `760dbd3`; no security-agents change after `760dbd3`)
- Related subsystem(s): security-agents live provider, M3
- Summary (facts, not assumptions): Readiness audit on main. Focused M3 suites: 76 passed, 11 skipped (the skips are opt-in live tests). The security-agents workflow is green on `760dbd3`. A scripted replay report shows Probe's trace with the listing call and exact check parameters, and no fixture tokens, `Bearer` strings or `sk-ant` patterns. No blocker found. Not yet proven: any live role after Probe.
- Interface requested/proposed (field-level types/example payload): none.
- Breaking change? migration/test impact: none.
- Action required by recipient: with the owner's explicit approval, run once:
  ```
  cd security-agents
  RUN_LIVE_LLM_EVAL=1 LIVE_SEVEN_MAX_USD=6 ../.venv/bin/python -m pytest -q -m live tests/test_live_provider.py -k seven_roles -s
  ```
  Operator checklist:
  1. `git log -1 --oneline` shows main at or after `760dbd3`.
  2. `ANTHROPIC_API_KEY` is exported in this shell only. `live_gateway_from_env` reads the environment, not `.env`. Do not paste it anywhere else.
  3. Use `LIVE_SEVEN_MAX_USD=6`. Each role's budget is checked before every turn, so each role can exceed its share by its final turn. 6 leaves headroom under a real $8 ceiling.
  4. Target: owned `examples/payments-lite` only, local-process sandbox (CLI `--i-have-authorization`, auto-approve). No external network.
  5. Keep `tests/artifacts/live/*-seven_roles_end_to_end.json` (gitignored). Post its per-role status, live turns and tools, states, usage (USD), findings, and Probe's `tool_trace` in a reply message.
  6. A failure is evidence too. Do not re-run without the owner's approval.
- Response-by milestone (not invented clock time): M3.
- Evidence: `security-agents/tests/test_m3_live_probe_discovery.py`, `tests/test_e2e_replay.py::test_report_carries_a_bounded_redacted_tool_trace_per_run`.
