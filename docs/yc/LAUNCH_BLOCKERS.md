# Launch blockers (product view)

Date: 2026-10-31, `main` @ `4271503e`. This list is for the **first controlled pilot** and the
**first paid customer**. The release gate (what may ship) is Codex's
[#739](https://github.com/adamissac/ari-ai/pull/739) `YC_BLOCKERS.md`; backend evidence is Devin's
[#744](https://github.com/adamissac/ari-ai/pull/744). Items from those are referenced, not
restated. Severity: **S0** blocks any pilot · **S1** blocks a paid/self-serve launch · **S2** post-launch.

## Blocking a controlled pilot (S0)

| # | Blocker | Evidence | Owner | Done when |
|---|---|---|---|---|
| L1 | Hosted backend down | `/healthz`, `/readyz` → 404 "Application not found" at 2026-10-31T17:09Z (this session); `/api/frontend-version` → `backendReachable:false`, frontend `c03a5501` | Railway operator (Adam / founder) | `/readyz` 200 and `sameCommit:true` on the `main` SHA |
| L2 | No live hosted assessment ever completed | `RAILWAY_AND_GITHUB_APP.md`: "Live production run verification remains outstanding" | Devin, founder approves spend | One assessment URL on a company-owned staging repo with a live model, ≥1 confirmed finding, evidence opens |
| L3 | Release-gate safety fixes unmerged (redaction #694, release checker #695, disconnect/review #693/#694, restart #725, watchdog #723) | #739 items 1–3, #744 | PR owners; Codex certifies | Merged in #744's order; Codex records GO for the union |
| L4 | Branch protection on `main` not visible / not requiring CI | #739 item 2 (protection API 404) | Repo admin (founder) | Required checks configured and confirmed |

## Blocking a paid or self-serve launch (S1)

| # | Blocker | Owner | Done when |
|---|---|---|---|
| L5 | No team workspace (invite a teammate) | Devin (backend) + Claude (UI) | An owner invites by GitHub login; invitee signs in and sees the org; cross-org test added |
| L6 | No plan/usage visibility or limit enforcement | Devin + Claude, after F1 | Org sees plan, repositories used, assessments used this period; limits refuse with the existing quota error |
| L7 | Validated findings only for Python HTTP services | Founder decision F3 | Pilot criteria say Python; or JS/TS validation scoped as its own project |
| L8 | Outage detection on `/readyz` with a human on call | Adam (#723 W1/W2) | Watchdog probes `/readyz`; missing token is reported; alert reaches a named person |
| L9 | Pricing surfaces disagree (deck vs `/pricing`) | Founder F1 | One model on every surface |
| L10 | First-session UX and honest outcomes unmerged | Claude (#740), Devin (#696) | Both merged after review |

## Not blocking (S2)

Notifications for pending approvals; self-serve deletion; glossary pass; finer coverage record;
`SNAPSHOT_NOT_READY` regression-registration dead jobs (S1 if they turn out to drop regression
tests for verified fixes — confirm first); closing the ~40 no-op status PRs.

## Explicitly out of the launch

Auto-commit delivery, Defense Lab / RL / first-responder, enterprise SSO, audit exports beyond
SARIF/RoE, multi-region, per-tenant databases.
