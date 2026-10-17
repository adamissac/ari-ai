# MSG: Owner-requested transparent navigation and warm headline refinement
- ID: `20261017T190117Z-sarosh-to-vihaan-nav-and-warm-glow`
- From: sarosh
- To: vihaan, sai, all
- Kind: integration
- Timestamp (UTC): 2026-10-17T19:01:17+00:00
- Branch: `feat/sarosh/ari-frontend-polish` (local `/tmp/ari-website-polish`)
- Summary: Removed logo/link white cards, borders and shadows. Pricing remains orange.
  Per-control nearest-surface contrast and subtle translucent hover preserve readability.
  Homepage headline gains only warm off-white text and three diffuse ember shadows;
  content, structure, spacing, CTAs, workflow pills and background remain unchanged.
- Evidence: Lint/typecheck/transport build/demo-only production build passed; 215 unit
  tests; 5 browser checks across 1440/1024/390/320px and reduced motion. Dark/light/dark
  contrast, transparent backgrounds, hover and routes checked; desktop/mobile rendered
  views inspected. No browser warnings/errors observed. Full backend e2e not rerun.
- Action: Local review only; no push/PR/deployment. Screenshots external to Git at
  `/tmp/ari-nav-glow-screens`.
