# 02 — Problem and users

Status: **specified**, based on team assumptions. None of the statements below
has been validated through user interviews yet (RQ-010 in
[research/RESEARCH_QUESTIONS](research/RESEARCH_QUESTIONS.md)).

## The problem, stated precisely

1. **Correctness and security are reviewed separately, without intent.** A
   static analyzer can say "this query is unparameterized" but not "this endpoint
   lets one customer read another customer's payments", because it does not know
   the second thing is forbidden.
2. **AI reviewers assert; they do not prove.** LLM review comments are cheap to
   produce and expensive to trust. Engineers ignore them after a few false alarms.
3. **Security testing is periodic.** Pentests happen yearly or before a big
   customer; code changes daily.
4. **Fixes are not closed loops.** A finding becomes a ticket, a fix, maybe a
   test. Nobody re-runs the original check against the fix, and nothing stops the
   bug from coming back.
5. **Runtime alerts are disconnected from code.** An anomaly in production is
   hard to tie to the commit that made it possible.

## Personas

### P-1 "Maya", tech lead at a 12-person startup
- Owns a Python/TypeScript SaaS; no security engineer.
- Needs: confidence that PRs do not break authorization or core flows; findings
  she can reproduce in minutes; fixes she can review like any PR.
- Will not tolerate: noisy alerts, tools that need weeks of tuning, anything that
  touches production without asking.

### P-2 "Dev", application security engineer at a mid-size company
- Responsible for 40 services; triages scanner output all day.
- Needs: validated findings with evidence and attack-path context; a record of
  what was tested and under which authorization.
- Will not tolerate: tools that cannot explain why something is exploitable.

### P-3 "Sam", individual developer / hackathon judge
- Evaluates the product in minutes.
- Needs: a clear story, a live loop that visibly works, honesty about limits.

## Jobs to be done

| Job | Persona | Pillar |
|---|---|---|
| "When I open a PR, tell me if it broke intended behavior, with a failing test." | Maya | P1 |
| "Show me which suspected vulnerabilities are real, with proof I can re-run." | Dev | P2 |
| "Give me a fix I can review, and prove it fixes the issue without breaking anything." | Maya, Dev | P1, P2 |
| "When the code or traffic changes, re-check what matters and tell me." | Maya, Dev | P3 |
| "Show me what was tested, under whose authorization, and what the system did." | Dev | cross-cutting |

## Key user journeys (MVP)

1. **Connect & authorize**: sign in with GitHub → choose a repo → register an
   AuthorizedScope (sandbox target built from the repo) → approve it.
2. **First assessment**: start assessment → watch progress timeline → review
   findings grouped by status → open a finding's evidence chain.
3. **Repair**: approve patch generation for a finding → inspect diff and
   Verify's evidence → open a PR (human click) → merge in GitHub (outside the
   platform).
4. **Stay secure**: a later push touches the payments route → monitoring flags
   the affected expectation → targeted re-assessment runs → regression test from
   the earlier fix fails/passes → user is notified.

Screens for these journeys: [14](14_FRONTEND_UX_DESIGN.md).

## Assumptions to validate

| ID | Assumption | Validation method |
|---|---|---|
| A-1 | Small teams will register a sandbox target built from their repo | Design-partner interviews |
| A-2 | Evidence links measurably raise trust vs. plain LLM review | A/B in user tests |
| A-3 | Users accept a human approval step before patch generation | Interviews, usage data |
| A-4 | Python web services are a sufficient first wedge | Market sizing, interviews |
