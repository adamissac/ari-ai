# Srihith → Adam, Sai, Vihaan: agent replay order, calmer agent map, Lab palette, page transition

Branch `claude/wizardly-mccarthy-hni97r` (frontend only; no contract or backend change). The landing page is untouched: it is pixel-identical to `089fc77` at 1440 and 390 px, motion on and off. The only differences are timed animations and #290's nav change.

- **Adam: demo replay logic (`lib/demo/agent-map.ts`).**
  - The red team (Scout, Probe) looks around. Parts it tested wait for Probe's verdict ("Tested · waiting for proof").
  - Once Probe is done, the confirmed part turns `issue` and every other tested part reads "No issue".
  - Trace, Diagnose, Patch, Fortify and Verify are now pinned to that red part. Before, Fortify's guard rule landed on the edge gateway, and Verify's request "as cus_b" landed on auth, both already marked clear.
  - The red part becomes `fixed` only when Verify accepts.
  - Clean commits stop after the red team.
  - Sandbox `http.request` steps map to the changed service.
  - New exports: `issueComponent`, `redTeamEnd`, `isRedTeam`. New state: `scanned`. `PHASES` is now Red team / Trace / Blue team / Verify.
  - Unit tests are in `tests/unit/agent-map.test.ts`.
- **Adam: commit view.**
  - Opens on Overview.
  - The Code review tab shows everything in place, with no `<details>`.
  - The agent map markup and CSS are rebuilt (one surface, agents grouped by phase, line icons, white transport).
  - All `data-testid`s used by `demo.spec.ts` are kept.
- **Sai: Defense Lab.** All overrides are scoped to night pages at the end of `globals.css`; your rules are untouched.
  - The map is warm ink instead of teal.
  - `node-graph.tsx`: the attacker/defender markers now sit inside each node's card (top-left / top-right). The "IMPORTANT/APPLICATION SERVICE" caption is replaced by "Critical" or the attacker stage. Cards are `y=-60, h=132` so two stacked nodes (160 apart) no longer collide. Texts asserted by `node-graph.test.tsx` are kept.
- **Vihaan:**
  - `components/route-transition.tsx` plays the intro's look (mark, %, load bar) between parts of the site.
  - It does not play within a part, never plays into `/`, and is skipped under reduced motion and `navigator.webdriver`, so e2e is unaffected.
  - Primary buttons on night pages are white with an ember hover, like the hero CTA.
  - `agent-relay.tsx` tiles are hairline with a status dot; `data-status` and the test ids are unchanged.
