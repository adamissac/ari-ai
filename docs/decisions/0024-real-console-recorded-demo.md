# ADR-0024: The access-code demo uses the real console with recorded fixtures

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-11-03 |
| Deciders | Adam (product owner request recorded in session); team ratification pending |
| Supersedes | ADR-0013 points 1 and 3 |

## Context

The independent `/demo` organization/repository/replay UI and hand-written account
records can drift from the current Ari console. Investor walkthroughs should show the
same Analytics, Commits, Findings, Approvals, Settings, and assessment pages as the
product, using sample records captured from the real API.

## Decision

The access-code gate opens the real console at the sample project's Analytics page.
In demo view, `api()` selects an in-browser transport that serves captured API
responses from `frontend/lib/demo/console/fixtures.json`. The capture script renames
the recorded company, repository, people, and file paths consistently. Known
non-200 responses are retained and replayed with their captured status and envelope.
Unknown GETs return a demo-specific 404; mutations return permission denied. The
transport never calls the backend.

The existing access-code check remains unchanged. Every console page displays a
persistent sample-data banner. Demo actions remain disabled; exit clears both demo
cookies and returns to the public home page. Fixtures and labels are illustrative,
not claims about customer activity.

## Consequences

- The demo follows the real console UI and runtime contracts rather than a parallel
  presentation layer.
- Fixture capture and schema-decoding tests are required when the console's API reads
  change.
- A captured non-200 remains visible as-is; it must not be silently converted into a
  successful sample response.
- The demo account remains gated, visibly labelled, offline, and read-only.
