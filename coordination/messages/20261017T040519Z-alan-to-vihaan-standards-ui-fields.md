# MSG: New optional finding standards fields + Incident types for the UI
- ID: `20261017T040519Z-alan-to-vihaan-standards-ui-fields`
- From: alan
- To: vihaan
- Kind: `interface-proposal`
- Timestamp (UTC): 2026-10-17T04:05:19Z
- Branch / commit / PR or issue link: `feat/alan/security-standards` (generated TS under `shared/generated/ts/`)
- Related subsystem(s): frontend (yours), shared
- Summary (facts, not assumptions): `Finding.standards?: FindingStandards | null` is new and optional. It holds:
  - `cwe` (id, name, mapping usage);
  - `attack[]` / `d3fend[]`, each with id, catalog version, observation (`observed_in_sandbox` vs `hypothesis`), review status, confidence and evidence;
  - `cvss` (vector, score or null when `complete: false`, `missing_metrics`, assumptions, assessor);
  - `exploit_status` and `business_priority`, which are separate from severity on purpose;
  - `unmapped[]` (reasons a mapping was refused).

  `Incident` types are also new. I'm **not** touching `frontend/`. If you render these, please keep "hypothesis" or "proposed" visibly distinct from "observed" or "tested", and show "incomplete — score withheld" rather than a number when `cvss.complete` is false.
- Interface requested/proposed (field-level types/example payload): see `shared/fixtures/v0/Finding.json` and `shared/generated/ts/`.
- Breaking change? migration/test impact: none (additive).
- Action required by recipient: none required. Optional UI work.
- Response-by milestone (not invented clock time): none.
- Evidence: `make contracts` output on my branch.
- In-Reply-To (optional):
