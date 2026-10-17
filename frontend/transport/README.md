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
