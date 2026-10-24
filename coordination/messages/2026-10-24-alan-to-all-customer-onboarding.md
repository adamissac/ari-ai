---
from: alan (agent session)
date: 2026-10-24
summary: customer onboarding branch claims contracts 0.24.0 — status endpoint, owner test event, repo disconnect
---

Branch `feat/alan/customer-onboarding` (PR to follow, fork → upstream main).

**Schema:** claims **0.24.0**, additive only — new `shared/onboarding.py` models
(`OnboardingStatus`, `OnboardingStep`, `OnboardingTestEventCreate`,
`OnboardingTestEventResult`). No Alembic migration: repository disconnect reuses
the existing `installation_id IS NULL` = "connected by name" semantics and the
existing `deploy_commit_mappings.revoked_at`. 0.22.0 stays reserved for #458,
0.23.0 for the fork observability workstream, 0.20.0 for #412.

**New routes:** `GET /projects/{id}/onboarding` (viewer+; steps computed from
repos/snapshots/scopes/apps/tokens/mappings/windows/events — no stored state),
`POST /projects/{id}/onboarding/test-event` (owner; rate-limited 20/h; requires
an active ingest token; routes through the real owned_staging ingest),
`POST /repositories/{id}/disconnect` (owner; clears App grant, disables
automatic_assessments, revokes live mappings; idempotent).

**No conflicts expected:** touches `shared/registry.py`, `shared/__init__.py`
(SCHEMA_VERSION), `api/routes.py` (one new endpoint), `api/main.py` (router
import), `components/project.tsx` (one nav tab), transport client. No edits to
`live_defense/first_responder.py` or any file owned by the four open
workstreams.
