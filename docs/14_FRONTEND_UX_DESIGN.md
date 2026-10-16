# 14 — Frontend UX design

Status: **specified**. Directory: `frontend/`. Stack: Next.js (App Router),
React, TypeScript (strict), Tailwind. Types generated from `shared/`.

## UX principles

1. **Status is always visible.** Every claim carries a badge: `Hypothesis`,
   `Validated`, `Refuted`, `Verified`, `Rejected`, `Stale`. Colors are paired with
   text and icons (not color alone).
2. **Evidence is one click away.** Any finding, expectation or verdict links to
   its evidence chain.
3. **Humans decide consequential steps.** Approval actions are explicit, named
   buttons with a summary of what will happen; never default-on toggles.
4. **No AI theater.** Neutral, professional visual language; no fake typing
   animations; progress reflects real orchestrator states.
5. **Honest empty and error states.** "No findings validated" is distinct from
   "assessment failed".

## Information architecture

```
/                         Landing (signed out) / project list (signed in)
/projects/[id]            Project overview: repos, last assessment, open findings, monitoring feed
/projects/[id]/scope      Authorized scopes: request, approve, revoke
/projects/[id]/expectations  Behavioral expectations: review, confirm, edit
/projects/[id]/assessments/[asm]  Live assessment timeline
/projects/[id]/findings   Findings list (validated+), separate Hypotheses tab
/projects/[id]/findings/[fnd]  Finding detail: evidence chain, attack path, patches
/projects/[id]/approvals  Approval inbox
/projects/[id]/monitoring Events feed + RL recommendations (labeled simulation-derived)
/settings                 Budgets, monitoring policy, GitHub App installation
```

## Key screens

### Live assessment timeline
- Horizontal state rail mirroring [08](08_AGENT_ORCHESTRATION.md) states.
- Per-agent lanes with AgentRun cards (status, duration, tokens, cost).
- Hypotheses fan out under Probe with outcomes.
- Budget meter (tokens and USD) with the cap.
- Data via SSE; reconnect with `Last-Event-ID`.

### Finding detail
- Header: title, status badge, severity with factors tooltip, affected entry point.
- **Evidence chain** (vertical): Expectation → Hypothesis (Scout, cited code) →
  Validation (Probe, sandbox run log excerpt) → Attack path (steps marked
  verified/unverified) → Root cause → Patch diff → Verification checks (pass/fail
  each) → Hardening.
- Code excerpts render with line numbers and link to GitHub at the snapshot SHA.
- Actions: Approve remediation, Open PR (after verification), Accept risk.

### Approval inbox
- Each item: what is being approved, who requested, scope/finding summary, what
  the platform will and will not do, expiry.

### Monitoring
- Event feed with impact summaries ("push abc123 touched `get_payment`, which has
  1 verified finding → regression test re-run: passed").
- RL panel: recommended action, margin, policy version, and the fixed caveat text
  "Recommendation from a policy trained in simulation. Not applied automatically."

## Component conventions

- Shared UI primitives in `frontend/components/ui/`; feature components by route.
- Server components for data fetch where possible; client components for SSE.
- API client generated from OpenAPI; no hand-written fetch types.
- Frontend never calls Claude or any LLM directly.

## Accessibility & responsiveness

WCAG 2.1 AA targets for core flows; keyboard-navigable timeline and diff views;
min width 360px for read-only views (approvals usable on mobile).

## Demo considerations

A `?demo=1` flag may slow the SSE replay of a *recorded real run* for
presentation. It must display a "Replay of recorded run <id>" banner. Fabricated
runs are not allowed ([20](20_DEMO_SCRIPT.md)).
