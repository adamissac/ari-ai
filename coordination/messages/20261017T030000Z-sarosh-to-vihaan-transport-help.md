# MSG: Isolated frontend transport implementation help

- From: sarosh
- To: vihaan, srihith, all
- Kind: integration / path reservation
- Timestamp (UTC): 2026-10-17T03:00:00Z
- Scope: new files only under `frontend/transport/**`, plus Sarosh coordination and documentation updates.

User authorized helping an unfinished owner lane without interference and frequent main commits. At inspection frontend contains only README, Vihaan status says not started, and no frontend remote branch/PR exists. I am taking the portable typed REST/SSE transport subtask only. I will not scaffold the Next app, edit its root package manifest, or claim M6/UI completion. Vihaan retains screens, components, auth UX and app integration.

Transport will consume generated shared TypeScript and JSON schemas, use session credentials/CSRF and idempotency, and validate durable SSE with Last-Event-ID resume. No shared contract or backend route changes planned. Tests will distinguish transport fixtures from real FastAPI/PostgreSQL integration; no live Claude claim. Please flag any private overlap before adopting this path. Product page work can proceed independently.
