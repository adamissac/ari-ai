# frontend/

Next.js 16 (App Router) + React 19 + strict TypeScript + Tailwind 4 dashboard for the
whole product. Every screen reads the control-plane API (`/api/v1`) or, for the Defense
Lab, a committed and schema-validated RL evaluation bundle. Nothing is generated or
simulated in the browser. Spec: [docs/14](../docs/14_FRONTEND_UX_DESIGN.md).

## What is implemented

| Route | Backed by |
|---|---|
| `/` projects, create project | `GET/POST /projects` |
| `/projects/[id]` one next step from the loaded records (connect a repo, approve a scope, run a review, open the run, or view results), then assessments, findings, repositories | `/projects/{id}/assessments`, `/findings`, `/scopes`, `/repositories` |
| `/projects/[id]/scopes` request, approve (backend enforces a different member), revoke | `/projects/{id}/scopes`, `/scopes/{id}/approve`, `/scopes/{id}/revoke` |
| `/projects/[id]/assessments/[asm]` live timeline: state rail from states actually entered, selectable eight-agent view (job, recorded outcome, real tool calls, handoff), budget meter, remediation approval gate, cancel, durable event log, provider-mode banner | `watchAssessment` SSE (`Last-Event-ID` resume) + `GET /assessments/{id}` + 5 s polling fallback while running |
| `/projects/[id]/findings` validated / hypotheses / closed tabs | `/projects/{id}/findings` |
| `/projects/[id]/findings/[fnd]` evidence chain (expectation → Scout → Probe → Trace → Diagnose → Patch → Verify → Fortify), standards labels (CWE, CVSS, ATT&CK, D3FEND) from the persisted record, GitHub links at the exact SHA, line-numbered diff, Verify checks, status history, accept risk | `/findings/{id}`, `/findings/{id}/patches`, `/artifacts/{id}` (size-bounded, SHA-256 checked) |
| `/projects/[id]/approvals` inbox with will / will-not summaries | `/projects/{id}/approvals`, `/approvals/{id}/decision` |
| `/projects/[id]/monitoring` webhook/runtime event feed (simulated events labelled), impact sets, re-assessments, simulation-derived RL recommendations + explanations, imported RL evaluations | `/projects/{id}/events`, `/reassessments`, `/defense-recommendations`, `/rl-evaluations` |
| `/projects/[id]/expectations` snapshot picker (ready snapshots only), behavioral expectations with status filters, sources at file:line, confirm / conflicting / reject with a reason and `expected_revision` (409 on stale view), decision history | `/repositories/{id}/snapshots`, `/snapshots/{id}/expectations`, `PATCH /snapshots/{id}/expectations/{exp}`, `/decisions` |
| `/projects/[id]/incidents` open (simulated by default, labelled), NIST lifecycle rail, triage, assign owner, transitions, two-person approval gates (requester cannot decide), timeline with CSF refs; closure panel: link findings and accepted verifications, closure criteria satisfied with hash-pinned patch/regression artifacts, lessons learned (Fortify regression evidence), communications (RS.CO-02/03, RC.CO-03), closure readiness list | `/projects/{id}/incidents`, `/incidents/{id}`, `/incidents/{id}/actions` |
| `/projects/[id]/settings` project name, languages, default + monitoring budgets, trigger policy (enabled, coalescing interval, record-only globs); validated client-side, owner-only on the backend | `PATCH /projects/{id}` |
| `/lab` Defense Lab: provenance (path, SHA-256, checkpoints, seeds), held-out metrics with 95% CI and n, topology, episode replay with reward components; hidden attacker stage only as labelled simulation ground truth | `rl-defense/results/protocol-*/defense_lab.json`, validated server-side against `rl-defense/fixtures/defense_lab.schema.json` |

Same-origin API: `app/api/v1/[...path]` proxies to `BACKEND_ORIGIN` at request time
(no CORS; the backend's `SameSite=Lax` cookie and CSRF header work as designed;
SSE streams unbuffered). Types and runtime validation come only from
`shared/generated` through [`transport/`](transport/README.md).

Honesty rules enforced in code: backend offline → "Backend unreachable"; a response
that fails the shared JSON Schema → "Backend response rejected" (never rendered);
non-`live` `provider_mode` runs are labelled "Not a live-provider run"; fixture mode
exists only behind `NEXT_PUBLIC_DEMO_FIXTURES=1` and shows a permanent DEMO DATA banner.

## Commands

Node ^22.22.2 or ≥ 24.15 (jsdom 30 for the unit tests). From `frontend/`:

```sh
npm ci --prefix transport && npm run build --prefix transport   # after every contract regeneration
npm ci
npm run lint && npm run typecheck && npm test && npm run build
BACKEND_ORIGIN=http://127.0.0.1:8000 NEXT_PUBLIC_DEV_LOGIN=1 npm run dev   # with `make dev` running the API
../.venv/bin/python tests/e2e/stack.py                                # browser e2e, see below
```

`NEXT_PUBLIC_DEV_LOGIN=1` only shows the development sign-in form; the backend still
refuses it unless `APP_ENV` is development/test and `AUTH_DEV_LOGIN_ENABLED=true`.

## Browser e2e (`tests/e2e/stack.py`)

Starts real FastAPI + PostgreSQL migrations + the job worker + `next start`, seeds two
org owners, a project and the `examples/payments-lite` repository binding (an operator
registry the UI cannot set), then runs Playwright. The journey test drives the rendered
UI: request scope → second user approves → start assessment → live SSE timeline →
second user approves remediation → reviewer + seven security agents complete → security
finding evidence chain → hash-checked diff → Verify accepted → state survives reload.
Also: signed GitHub push appears in monitoring, create project / connect repo,
backend-offline and contract-violation states, Defense Lab, bundle path refusal.

Model replies come from the backend's own TEST-ONLY scripted transports (the same ones
as `backend/tests/test_unified_assessment.py`), so every agent run is persisted with
`provider_mode="fake"` and the UI says so. Everything else — HTTP, cookies/CSRF, queue,
git checkout, reviewer test execution, local-dev sandbox checks, Patch/Verify, artifacts,
SSE — is real. No API key is read. Screenshots of the executed run are written to
`test-results/evidence/`.

Env: `TEST_DATABASE_URL` (admin URL of an existing Postgres; default embedded pgserver,
which cannot start from a path containing spaces), `E2E_BROWSER_CHANNEL=chrome` to use an
installed Chrome instead of Playwright's Chromium, `E2E_SKIP_BUILD=1` to reuse `.next`.

## Known gaps (not hidden in the UI)

- No backend endpoint serves the Defense Lab bundle; the Lab reads the committed artifact.
- A finding whose assessment has no indexed snapshot can only show expectation ids.
- Lessons learned stay blocked, and the closure panel says so, when Fortify did not record a regression-test artifact.
- GitHub links stay off when an assessment scope names more than one repository. Findings still do not carry a repo id.
- Live-provider (`provider_mode=live`) runs have not been exercised through the UI.
- The project journey cannot see a phase the latest assessment's event log did not record. A log longer than the 500-event page can leave a later phase unmarked.
