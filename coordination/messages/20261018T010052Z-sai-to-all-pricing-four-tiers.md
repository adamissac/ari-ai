# Sai → all: pricing is now four plans (owner's table)

/pricing now shows Founder $49.99, Growth $129.99 (recommended), Scale $359.99 and Enterprise (contact us). Each plan lists full assessments per month (7 / 20 / 60 / custom), assessed source lines per month (1M / 5M / 20M / custom) and the price per included assessment ($7.14 / $6.50 / $6.00 / custom).

The per-assessment price is computed from price ÷ assessments, and a unit test pins it to the owner's table. The plan data lives in `frontend/lib/pricing.ts`. The seat-based "Team $40" plan and its seat FAQ are gone; a new FAQ defines assessed source lines. The page still says it's a preview and nothing can be purchased.

Note for #280 (pricing FAQ restyle): both PRs touch `app/pricing/page.tsx`, so whichever merges second needs a small rebase. Owner: Sai (frontend).
