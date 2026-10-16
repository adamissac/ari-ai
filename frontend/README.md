# frontend/

> **What exists: nothing yet (Phase 0).** This README defines future
> responsibilities. Spec: [docs/14](../docs/14_FRONTEND_UX_DESIGN.md).

## Purpose
The web dashboard: connect repos, register and approve scopes, watch
assessments live, inspect evidence chains, approve remediation, review patches
and verification, follow monitoring and RL recommendations.

## Responsibilities
- Screens and flows in [docs/14](../docs/14_FRONTEND_UX_DESIGN.md).
- Honest status presentation (hypothesis / validated / verified / rejected / stale).
- SSE client for live assessment progress.
- Accessibility (WCAG 2.1 AA target for core flows).

**Must not:** hold business logic, call Claude or any LLM, define its own API
types, render repository content as HTML.

## Interfaces
| Direction | Interface |
|---|---|
| Consumes | Backend REST `/api/v1` + SSE `/api/v1/assessments/{id}/events` ([docs/13](../docs/13_BACKEND_API_DESIGN.md)) |
| Types | Generated TypeScript from `shared/generated/ts` (never hand-edited) |
| Auth | Session cookie set by backend OAuth flow; CSRF header on mutations |

## Dependencies
- Upstream: `shared/` generated types (CORE-003), backend API (CORE-002+).
- Proposed stack: Next.js (App Router), React, TypeScript strict, Tailwind,
  ESLint, Prettier, Vitest + Testing Library, pnpm (RQ-008).
- Hosting (only if approved): Vercel free tier.

## Planned layout
```
frontend/
  app/                      # routes per docs/14 information architecture
  components/ui/            # shared primitives
  components/<feature>/     # evidence-chain, timeline, approvals, diff, monitoring
  lib/api/                  # generated client wrapper
  lib/sse/                  # SSE hook with Last-Event-ID reconnect
  tests/
```

## First tasks
UI-001 (scaffold), then UI-002…UI-007 ([HACKATL_TASKS](../docs/planning/HACKATL_TASKS.md)).

## Commands
None yet. Add install/dev/lint/test/build commands here and in
[CLAUDE.md](../CLAUDE.md) when UI-001 lands.
