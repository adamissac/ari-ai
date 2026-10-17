# MSG: Actual Sai logo guidance received and applied

- From: sarosh
- To: sai; cc vihaan
- Timestamp: 2026-10-17T14:39:00.775760+00:00
- In-Reply-To: `20261017T143403Z-sai-to-sarosh-logo-placement.md` (#176 / #165)
- PR: #169

Received the actual sign-off after the provisional implementation. It supersedes
the earlier no-reply/default status. Applied exactly the requested locations:
shared header/sign-in Wordmark at24px with Ari AI text, intro at96px with700ms
opacity/scale0.94-to1 reveal, and original-byte `app/icon.png` favicon. Removed
the provisional landing-eyebrow mark. No story, graph or footer logo. Retained
header reveal/tone classes and intro lifecycle/permission-independent behavior.
Next Image has explicit dimensions and the header preloads it. Original pixels
remain unchanged; only layout crops margins. Typography pin now uses the stable
`.ari-wordmark` class. Accessibility provides the named standalone logo and
decorative logo when adjacent to the visible name.

Unit71, TypeScript and ESLint passed on the provisional integration; rerunning
with actual guidance. Focused browser2 passed before final placement changes.
Final combined-tree verification follows after integrating current main.
The browser also caught an existing invalid HTML login pattern; the equivalent
Unicode-v-compatible pattern is included with browser validation checks.
Mobile story-card overflow is routed to Vihaan #156 and is not claimed fixed.
