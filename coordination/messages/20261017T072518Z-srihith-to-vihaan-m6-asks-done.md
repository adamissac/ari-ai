# MSG: Your M6 backend observations 1-2 and API asks (b) and (c) are done
- ID: `20261017T072518Z-srihith-to-vihaan-m6-asks-done`
- From: srihith
- To: vihaan (cc: alan, sai)
- Kind: `integration`
- Timestamp (UTC): 2026-10-17T07:25:18Z
- Branch / commit / PR or issue link: #65 (merged), #66 (merged), #67 (contracts 0.8.0)
- Related subsystem(s): backend host, API, shared contracts, frontend transport
- Summary (facts, not assumptions):
  1. **Lifecycle (#65):** after a hosted run, security findings now carry real `status` and `history`: `hypothesis→validated→diagnosed→patch_proposed→verified→hardened`, each with a `StatusChange` (actor `agent:orchestrator`, reason when one is known). The host refuses edges outside docs/12, and refuses claims without evidence: `validated` needs a confirmed ValidationResult, `verified` needs an accepted Verify of this finding's patch. SSE `finding_updated` events now include `from_status`.
  2. **Usage (#65):** `Assessment.usage.tool_calls` equals the sum of the runs' tool calls, and `sandbox_seconds` holds the Probe/Verify sandbox time.
  3. **(b) Snapshot list (#66):** `GET /api/v1/repositories/{repo_id}/snapshots?status=&limit=&cursor=` returns newest first in the standard `{items, next_cursor}` envelope with `Snapshot` items.
  4. **(c) DTOs (#67, contracts 0.8.0, additive):** `FindingDetail` (records are a discriminated union on `type`) and `AssessmentReport` are shared models, enforced as `response_model`. The wire fields are unchanged; you can swap your local part-mapping for `decode('FindingDetail' | 'AssessmentReport', ...)` when convenient.
  5. **(a)** I kept the `label` on defense-recommendations, since you already accept it explicitly.
- Interface requested/proposed: as above.
- Breaking change? migration/test impact: none. Transport is 21/21 against regenerated 0.8.0; frontend typecheck and vitest pass 23/23; real-stack Playwright passes 8/8 on #65.
- Action required by recipient: optional. Add transport methods for the snapshot list, and decode the two DTOs.
- Evidence: PR descriptions for #65/#66/#67, which list the commands run and their counts.
- In-Reply-To (optional): `coordination/messages/20261017T040659Z-vihaan-to-all-frontend-m6.md`
