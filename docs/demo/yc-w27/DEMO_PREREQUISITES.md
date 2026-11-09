# YC demo prerequisites

Everything below must be true **before** you record. If any line is not, use the
fallback in [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md#path-b--local-real-stack-scripted-model-replies) and say on screen
that model replies are scripted.

## Honesty rules (non-negotiable)

- The demo repository is **company-owned staging**, seeded with a known vulnerability
  (`examples/payments-lite`: payment-detail route without an ownership check, CWE-639;
  refunds can exceed the payment total, CWE-840). Say so out loud. Never call it a customer.
- Only show an assessment the platform actually ran. Do not edit, stage or composite results.
- If the assessment page says **"Not a live-provider run"**, it is scripted. Do not cut that
  banner out, and do not describe it as a live analysis.
- No customer names, logos, counts or activity anywhere in the recording.

## Primary path: hosted console (recommended)

| # | Check | Who | How to confirm |
|---|---|---|---|
| 1 | This PR and PR #696 are merged and deployed | Engineering | `https://ari-ai-lake.vercel.app/api/frontend-version` matches `main` |
| 2 | A company-owned GitHub repo (e.g. `<your-org>/payments-lite-staging`) contains a copy of `examples/payments-lite/target` | Founder | Repo exists, is private, and is listed under **Projects → your org** |
| 3 | The Ari GitHub App is installed on that repo only | Founder | GitHub → Settings → Installed GitHub Apps → Ari → *Only select repositories* |
| 4 | Setup completed for that repo, sandbox testing approved (Setup question 6), fix delivery **Ask me first** | Founder | Setup shows all eight questions **Saved** |
| 5 | **One live assessment completed the day before**, with findings and a verified fix | Founder + Devin | Its page shows **Completed**, **Live provider run**, and **What this check did** with ≥1 confirmed finding and ≥1 fix accepted by an independent re-test |
| 6 | You have the URL of that assessment page bookmarked | Founder | Opening it shows the same result with no re-run |
| 7 | Anthropic spend limit set; budget per assessment is visible in **Settings → Default assessment budget** | Founder | — |

Item 5 is the gating item: live production run verification is still outstanding
(see `docs/deploy/RAILWAY_AND_GITHUB_APP.md`). If it has not succeeded, use the fallback.

## Fallback path: local real stack, scripted model replies

- macOS/Linux laptop with Python 3.12, `uv`, Node `^22.22.2` or `>=24.15.0`, Git.
- From the repo root, once:

  ```sh
  uv sync --frozen --python 3.12
  (cd frontend && npm ci --prefix transport && npm run build --prefix transport && npm ci)
  ```

- No API key and no GitHub App needed. Every agent run is real (tests, sandbox checks,
  Patch, Verify, persistence); only the model's replies are scripted, and the UI labels it.

## Recording setup

- Browser window 1440×900, zoom 100 %, light background behind the window, notifications off.
- Signed in before you hit record. Close unrelated tabs.
- Screen recorder at 1080p, 30 fps; record voice separately if possible.
