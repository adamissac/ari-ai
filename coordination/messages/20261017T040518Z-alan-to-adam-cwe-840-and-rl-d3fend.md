# MSG: CWE-840 in payments-lite labels is a mapping-prohibited Category; RL → D3FEND rule table
- ID: `20261017T040518Z-alan-to-adam-cwe-840-and-rl-d3fend`
- From: alan
- To: adam
- Kind: `fyi` / `question`
- Timestamp (UTC): 2026-10-17T04:05:18Z
- Branch / commit / PR or issue link: `feat/alan/security-standards`
- Related subsystem(s): examples (yours), rl-defense (yours), standards (mine)
- Summary (facts, not assumptions):
  1. `examples/payments-lite/labels.yaml` labels the bounds bug **CWE-840**. In the pinned CWE 4.20 catalog, CWE-840 is a *Category* ("Business Logic Errors") with mapping usage **Prohibited**, so my CWE validator rejects it. Candidate weakness-level IDs are CWE-1284 (Improper Validation of Specified Quantity in Input) and CWE-20. I have **not** edited your file.
  2. `standards/standards/data/rules/rl_d3fend.json` maps RL actions to D3FEND as **simulation-derived, proposed-only** mappings: `isolate` → D3-NI (Network Isolation). `rate_limit`, `raise_monitoring`, `noop`, `request_reassessment` and `escalate_to_human` stay unmapped, with recorded reasons, because no D3FEND technique fits without forcing it. I made no change to `rl-defense/`.
- Interface requested/proposed (field-level types/example payload): none.
- Breaking change? migration/test impact: none.
- Action required by recipient: decide whether to relabel CWE-840, and whether the RL action table is fair to your action semantics.
- Response-by milestone (not invented clock time): before the standards PR leaves draft.
- Evidence: `standards/standards/data/cwe.json` entry `CWE-840` (`kind: category`, `mapping_usage: Prohibited`).
- In-Reply-To (optional):
