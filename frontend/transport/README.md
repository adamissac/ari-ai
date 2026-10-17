# Frontend transport

Isolated support package for Vihaan's app; no pages or React dependency. Install
with `npm ci --prefix frontend/transport`, test with `npm test --prefix frontend/transport`.
Node 22+ is required for the build/test JSON import attributes. Browser consumers
use the built ESM exports; compile with `npm run build --prefix frontend/transport`
after every shared contract regeneration. Generated canonical types and schemas
are compiled/copied into ignored `dist/`; do not edit those outputs.

```ts
import { ApiClient } from '@hackatl/frontend-transport';
const api = new ApiClient({ baseUrl: 'http://localhost:8000/api/v1' });
const session = await api.session(); // cookie session, CSRF stays in memory
const assessment = await api.assessment('asm_12345678');
```

The Next app can depend on `file:./transport`. Configure its backend base URL and
CORS/cookie settings per backend documentation. No tokens enter localStorage.
OAuth remains a browser navigation to backend `/auth/github/login`; `devLogin`
only invokes the explicitly enabled development endpoint. Mutations require a
loaded session, carry CSRF, and never retry automatically. Starting assessments
and snapshots requires a caller-created idempotency key, reused for retries of
the same user action. Scope/repair approvals are explicit calls, never automatic.

Network DTOs are validated against `shared/generated/contracts.schema.json`
with AJV; no local entity definitions. Complete fields are required to match the
generated TypeScript DTOs and backend model serialization. `ProtocolError`
indicates malformed data; `ApiError` includes canonical error code/request ID.
Error validation never includes the response payload in exception messages.

Current scope is transport only. App integration, browser auth UX, rendered
loading/error states, and M6 acceptance are not complete.

## Durable SSE

```ts
import { watchAssessment } from '@hackatl/frontend-transport';
const controller = new AbortController();
for await (const event of watchAssessment(api, assessment.assessment.id, {
  after: lastRenderedSequence,
  signal: controller.signal,
  onConnection: state => updateConnectionLabel(state),
})) {
  renderPersistedEvent(event); // text, never innerHTML; idempotent by seq
  lastRenderedSequence = event.seq;
}
// On unmount: controller.abort(); handle rejected AbortError in the caller.
```

Fetch streaming is used instead of EventSource so resume headers and abort are
explicit. Reconnect sends both `Last-Event-ID` and `after`, accepts only matching
assessment/type/sequence envelopes, and ignores validated duplicate sequences.
Schema errors and 4xx permissions fail immediately; transport failures, 429 and
5xx have at most five retries with capped exponential delay (configurable).
`onConnection` exposes connecting/connected/reconnecting/completed/aborted/failed.
A closed socket is not completion: a terminal event or fetched persisted terminal
assessment is required. Terminal means the run ended, including failed/cancelled;
render the actual assessment state, not a generic success badge.

Cursor ownership stays with the consumer: save the last successfully rendered
sequence across remounts. Throwing from the consumer does not auto-replay its UI
side effects. Aborting cancels fetch/body/reconnect delays. Framing supports
chunked UTF-8, CR/LF/CRLF, multiline data, comments, retry controls and discards
incomplete EOF frames. JSON bodies default to 8 MiB and SSE frames to 1 MiB.

## Real backend proof

After the root Python dev workspace is installed (`uv sync --dev --all-packages`),
run `npm run test:integration --prefix frontend/transport`. This starts real
FastAPI HTTP with real PostgreSQL migrations in a uniquely named temporary DB on
`.dev/pgtest`, and drops only that DB afterward. It never runs a worker or target
code and never calls a model. Node uses a test-only cookie jar; this does not
prove browser CORS/SameSite or any rendered page behavior.

The three integration subtests cover session/CSRF/tenant denial, two-human scope
approval and idempotent assessment creation, then cancellation with three durable
events and resume from seq 1 to seqs 2/3. Empty terminal replay is confirmed via
persisted assessment state. Assessment creation unwraps the existing backend
`{assessment, job_id}` envelope and returns its canonical `Assessment`; job
metadata is not consumed. Snapshot creation currently ignores idempotency headers
and deduplicates by repository/commit in the backend.

## Standards and incidents

`incidents`, `createIncident`, `incident`, and `actOnIncident` use the canonical DTOs and existing cookie/CSRF flow. `incident` returns the typed `{incident, standards}` envelope. `mappingLabel`, `findingStandards`, and `incidentLabel` preserve catalog versions, proposed/hypothesis/simulation labels, vectors, assumptions, and unscored gaps. Render returned values as text. These helpers are not mounted dashboard pages; the frontend owner retains that integration.
