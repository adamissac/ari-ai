# MSG: Owner-authorized ARI frontend release to main
- ID: `20261017T191409Z-sarosh-to-all-ari-frontend-main-release`
- From: sarosh
- To: all
- Kind: integration
- Timestamp (UTC): 2026-10-17T19:14:09+00:00
- Branch: `feat/sarosh/ari-frontend-polish`; product commits `391831a`, `ed37e30`, `b2961f9`
- Authorization: Owner explicitly requested pushing these changes to main.
- Scope: ARI branding/wordmark, centered warm hero, transparent contrast-aware
  navigation, home-only 100px reveal, inert hidden links and phone Menu disclosure.
- Evidence: Lint/type-check/demo-only production build passed; 219 unit tests and
  5 Chromium browser tests passed at 1440/1024/390/320px and reduced motion.
- Release base: `0f645c2`; working tree was clean, main is included in this branch.
  No backend/API changes in release diff. Earlier local-only messages are historical.
- Next action: Normal fast-forward push, confirm exact main SHA, inspect GitHub CI.
  The existing connected Vercel deployment follows main; no settings changed.
