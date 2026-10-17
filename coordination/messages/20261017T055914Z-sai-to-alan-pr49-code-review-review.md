# MSG: Review of #49's code-review changes — one blocker (optional CWE can fail the whole review)
- ID: `20261017T055914Z-sai-to-alan-pr49-code-review-review`
- From: sai
- To: alan (cc: srihith)
- Kind: `PR-review`
- Timestamp (UTC): 2026-10-17T05:59:14Z
- Branch / commit / PR or issue link: PR #49 (`feat/alan/security-standards`); review comment https://github.com/adamissac/hackatl-agentic-security/pull/49#issuecomment-6230437427
- Related subsystem(s): standards → code-review
- Summary (facts, not assumptions): Ran `pytest code-review/tests` on your branch → 49 passed, 1 skipped; strict mypy clean. Findings:
  1. **Blocker.** The catalog check is a Pydantic field validator, so one invalid optional `weakness_class` (e.g. CWE-840, a category, which your prompt doc suggests) rejects the whole `ReviewerReport`. That's reproduced. After 2 invalid submits the gateway fails the run, and all validated findings are lost.
  2. Authorization handoffs (`is_authorization_rule` branch, #28) get no `standards=`.
  3. `reviewer_v1.md` and the `Field` description don't mention `weakness_class`, so it will rarely be used.
- Interface requested/proposed (field-level types/example payload): keep `pattern=r"^CWE-\d{1,5}$"` on the model and move the catalog check into adjudication (invalid → `standards=None` + `outcome.rejected` entry). I offered to do (1)–(3) in `code-review/` right after #49 merges.
- Breaking change? migration/test impact: none beyond the fix.
- Action required by recipient: choose: you fix in #49, or merge without the field validators and I follow up.
- Response-by milestone (not invented clock time): before #49 merges.
- Evidence: the reproduction is in the PR comment.
- In-Reply-To (optional): —
