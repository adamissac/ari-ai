# Adam (Devin) → Vihaan: expectations / incidents / settings pages

Branch `devin/1792226026-frontend-gaps` adds `/projects/[id]/expectations`, `/incidents`, `/settings`
plus additive transport methods (`expectations`, `decideExpectation`, `expectationDecisions`,
`updateProject` via PATCH). Project tabs gained Expectations, Incidents, Settings. No shared
contract change. e2e: `tests/e2e/pages.spec.ts` (11/11 passing locally with stack.py).
Please review the PR; happy to rebase onto anything you have in flight.
