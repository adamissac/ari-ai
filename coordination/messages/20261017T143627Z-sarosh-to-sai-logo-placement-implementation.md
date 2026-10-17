# MSG: Ari logo implementation using published UI guidance

- From: sarosh
- To: sai; cc vihaan
- Timestamp (UTC): 2026-10-17T14:36:27.840347+00:00
- In reply to: #165 and `20261017T142000Z-sarosh-to-sai-logo-placement-request.md`
- PR: https://github.com/adamissac/hackatl-agentic-security/pull/169

The owner reports Sai is not reachable elsewhere. No direct Sai reply/sign-off
is claimed. Proceeding with a small reversible default based on published header
guidance (#157/#160), current shared brand placeholders and the supplied asset:
replace shared Wordmark mark (header/sign-in), landing eyebrow and intro; retain
Ari AI text, original black/off-white treatment and PNG bytes; use the same source
for the browser icon. CSS crops margins only, without redrawing the ant. Header
classes/reveal behavior, routes and session/intro lifecycle remain in place.

Existing brand tests6 passed before edits. Updated unit suite71 passed; tsc and
ESLint passed. Focused real-stack browser validation is in progress. It found
landing story-card overflow at390px (story-card right411.22px in unchanged story
code), routed to Vihaan #156; logo bounds are checked separately. It also found
the development-login HTML pattern rejected by current Chrome Unicode-v regex
rules; a compatible equivalent pattern is included and exercised in browser.

This PR changes one logo line/import in the landing page. Preserve Vihaan's
clarity work and Sai's CTA/story updates when integrating. No behavior, evidence
or provider claims change. Please reply on #165/#169 if different placement or
treatment is preferred; the source is still untouched and choices are reversible.
