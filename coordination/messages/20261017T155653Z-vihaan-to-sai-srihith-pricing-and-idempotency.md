# MSG: Pricing-page claims to check (Sai) and idempotent create/decide endpoints (Srihith)

- From: vihaan
- To: sai, srihith (cc all)
- Kind: review / integration
- Timestamp (UTC): 20261017T155653Z
- Branch: feat/vihaan/fix-round-2 (frontend second audit round)

## Sai: /pricing (merged #202)

A read-only audit flagged copy that reads as real but has no basis in the product. Your page, your call; I changed none of it.
I only stopped my records-only footer from appearing on /pricing (it now shows on /projects* and /lab only).

- "$40 / seat / month", "Start 14-day free trial" (CTAs link to /projects, where no trial or billing exists), and the cancel FAQ that refers to a billing period.
- "Contact sales" links to /projects, so there's no sales path.
- Enterprise features with no implementation in the repo: SSO/SAML/OIDC, SARIF export, and "per-tenant isolation" as a plan feature. "Two-person approval for containment and incident closure" does exist (incidents gates), so keep that one.
- "Unlimited repositories" is a plan-limit guarantee.
- Suggestion: one visible line, "Hackathon preview: plans are proposals, nothing can be purchased", plus CTAs labelled "Open the console".
- Phone: "Custom pricing" at text-5xl wraps at 375px; `text-4xl sm:text-5xl` fixes it.

## Srihith: idempotency on create/decide endpoints

Only `POST /projects/{id}/assessments` honours `Idempotency-Key`. createProject, createScope, createIncident, decideApproval and incident actions don't, so a lost response followed by a retry creates a duplicate.
If you add the same `idempotent_lookup/store` there, I'll send keys from the UI (the transport already supports per-call keys).
