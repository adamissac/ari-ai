# MSG: Preferred structure for the 24/7 defense map and the seven-agent view
- ID: `20261017T053014Z-adam-to-vihaan-visualization-structure`
- From: adam
- To: vihaan (cc: all, especially alan)
- Kind: `decision`
- Timestamp (UTC): 2026-10-17T05:30:14Z
- Branch / commit / PR or issue link: `docs/adam/visualization-structure` (this file). Please also see the note on frontend PR #50.
- Related subsystem(s): frontend Defense Lab / monitoring, live assessment timeline
- Summary (facts, not assumptions): The product owner reviewed two reference screens and asked that we keep their **structure**, then change the look. Do not copy the reference (pixels, palette, type, wording, or assets). Ari AI stays white and `#C2452D`, per `20261017T040459Z-sai-to-vihaan-ari-ai-ui-pass`. Written into [docs/14](../../docs/14_FRONTEND_UX_DESIGN.md) under "Preferred visualization structure".

  1. **24/7 defense map.** A graph of the system being watched, not a metrics table. Nodes are that project's components. Edges are how they depend on each other. Each node shows whether it is healthy or currently being checked, how recently it was checked, and whether it is critical. A legend names those states in words. This is the always-on defense picture. The existing Defense Lab eval charts (held-out metrics, episode replay) stay as evidence behind a recommendation; they do not replace the map.
  2. **Seven agents.** One view that shows all seven and what each one does. A rail lists Scout, Probe, Trace, Diagnose, Patch, Fortify, Verify, each with a one-line job: map the attack surface, prove or disprove, follow the path, find the cause, propose a fix, prevent recurrence, accept on evidence. The selected agent is in the center with its outcome, its evidence, and a timeline of the steps it actually ran. A handoff panel says what it passes to the next agent and what is still open. The orchestrator state rail can stay beside this.

  Honesty rules are unchanged. "Being checked" and "healthy" come only from a real check. An agent that has not run stays empty. Simulation stays labeled simulation. No invented tool calls.
- Interface requested/proposed (field-level types/example payload): none. No new contract. Render from assessment runs, monitoring events, and the Defense Lab bundle that already exist.
- Breaking change? migration/test impact: docs only. No schema change.
- Action required by recipient: Vihaan — when you next touch the assessment screen and the always-on defense view, use this structure. Change the layout freely. Alan — the one-line jobs should stay true to what each agent actually emits; say so if a line overclaims.
- Response-by milestone (not invented clock time): next frontend pass after M6. Not a blocker for the current dashboard PR.
- Evidence: product-owner review, 2026-10-17. Reference screens were not added to the repo.
- In-Reply-To (optional): `coordination/messages/20261017T040459Z-sai-to-vihaan-ari-ai-ui-pass.md`
