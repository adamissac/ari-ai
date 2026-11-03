# MVP scope — minimum commercial product

Status: **proposed for the first paid pilot** (2026-10-31). Supersedes the HackATL demo scope
(see git history of this file). Readiness and evidence: [YC_PRODUCT_READINESS](../yc/YC_PRODUCT_READINESS.md).

## Customer and problem

Startups and teams of ~2–30 developers without a security engineer. They ship fast and get
security work as noise (scanner maybes) or not at all. The MVP must deliver a **confirmed
vulnerability with executed evidence and a verified fix as a reviewable pull request**, in the
first session, without the team learning security tooling.

## The MVP in one sentence

A developer connects an authorized GitHub repository; Ari assesses a pinned commit in an
isolated sandbox, reports only findings an executed check confirmed (and says plainly what it
did not test), writes a fix only after a human approves, re-tests it independently, and delivers
it as a pull request the team merges.

## Proposed workflow vs. what the MVP commits to

| Step | MVP commitment | Today |
|---|---|---|
| 1. Connect an authorized repository | GitHub App on selected repos; owner approves a sandbox scope with an expiry | Implemented; hosted not verified |
| 2. Analyze for actionable security issues | Python HTTP services (FastAPI/Flask); JS/TS get functional review only | Implemented |
| 3. Prioritize with evidence | Confirmed / ruled out / unconfirmed, each linked to source spans and executed checks | Implemented; outcome panel in #740 |
| 4. Generate a proposed fix | After human approval only | Implemented |
| 5. Validate the fix | Independent Verify re-runs the attack and the existing tests | Implemented |
| 6. Reviewable pull request | PR delivery; Ari never merges or deploys | Implemented |
| 7. Monitor for regressions | Opt-in push-triggered re-assessment, rate-limited | Implemented; regression registration has an open question (C6) |

## In scope

Personal and invited team organizations (invites: G4); GitHub App; Python HTTP services up to
10,000 files / 32 MB; manual assessments and opt-in automatic reviews; sandbox-only scopes;
human approval before Patch; PR or in-app fix delivery; per-assessment budget and project
quotas; SARIF / rules-of-engagement export; weekly per-customer health report.

## Out of scope

Auto-commit delivery (exists, disabled for customers), Defense Lab / RL / first-responder,
staging or production targets, non-Python validation, enterprise SSO/SCIM, self-serve billing
(manual invoices first), third-party analytics, auto-merge (never), real-world RL action (never).

## Never cut

Scope check, sandbox isolation, the human approval gate, Verify independence, evidence links,
honest coverage and live/scripted labelling.

## Pilot success criteria (measured by `scripts/pilot/health_report.py`)

Per design partner, without inventing baselines: a completed first assessment in the first
session; ≥1 confirmed finding the team agrees is real; ≥1 verified fix merged by the team;
stale approvals and spend reviewed weekly. Report the observed numbers, including zeros.
