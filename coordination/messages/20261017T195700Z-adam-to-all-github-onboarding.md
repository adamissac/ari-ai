# Adam → all: GitHub onboarding and simulated attacks (feat/adam/github-onboarding)

- Srihith (backend): `/auth/github/callback` now redirects to `${FRONTEND_ORIGIN}/connect`, and
  an App-install return (`setup_action=install|update`, no state) restarts sign-in. Code is never
  exchanged without our state. `github_app_private_key_path` is now `SecretStr` and accepts PEM text.
- Vihaan/Sai (frontend): new `/connect` (organizations) and `/connect/[org]` (repositories);
  `/projects/[id]/simulate?repo=` is a labelled simulated attack + defense replay. The demo's
  `CommitAnalysis` moved to `components/demo/commit-analysis.tsx` (no behaviour change to /demo).
- Alan (security-agents): unchanged; live attacks still require a Python ASGI target. Other
  languages get the labelled simulation instead of a failed run.
- Deploy: Railway has all seven secrets staged (not yet deployed). Vercel stays DEMO_ONLY until
  real sign-in is verified.
