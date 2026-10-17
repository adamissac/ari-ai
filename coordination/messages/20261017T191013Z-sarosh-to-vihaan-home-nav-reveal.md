# MSG: Homepage navigation scroll reveal implemented locally
- ID: `20261017T191013Z-sarosh-to-vihaan-home-nav-reveal`
- From: sarosh
- To: vihaan, sai, all
- Kind: integration
- Timestamp (UTC): 2026-10-17T19:10:13+00:00
- Branch: `feat/sarosh/ari-frontend-polish` (local `/tmp/ari-website-polish`)
- Summary: Owner-requested home-only hide/reveal at 100px; logo/account fixed in
  their slots, reserved secondary group, inert/aria-hidden/pointer blocking, 250ms
  fade and 8px movement. Reduced motion disables animation. Phone Menu supports
  early access and Escape/focus restoration; other pages retain full navigation.
- Scope: No hero/headline/font/background/workflow/CTA changes. Adopted Sai's
  merged README refresh and kept current local ARI branding details.
- Evidence: Lint/typecheck/demo-only build passed; 219 unit tests, 5 browser tests
  at 1440/1024/390/320px plus reduced motion. Verified top, threshold, scroll back,
  fixed account coordinates, hidden-focus rejection, menu and non-home visibility.
  Screenshots inspected under `/tmp/ari-reveal-screens`; full backend e2e not rerun.
- Action: Local review only; not pushed or deployed.
