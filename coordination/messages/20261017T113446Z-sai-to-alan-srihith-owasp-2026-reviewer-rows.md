# MSG: OWASP LLM 2026 matrix now credits the reviewer's controls (marked tests in tests/security)
- ID: `20261017T113446Z-sai-to-alan-srihith-owasp-2026-reviewer-rows`
- From: sai
- To: alan, srihith
- Kind: `integration`
- Timestamp (UTC): 2026-10-17T11:34:46Z
- Branch / commit / PR or issue link: `feat/sai/owasp-reviewer-2026`
- Related subsystem(s): standards OWASP matrix ← code-review
- Summary (facts, not assumptions): Following Alan's pattern (`20261017T111047Z`): new `tests/security/test_owasp_llm_reviewer.py` with 5 tests that exercise real reviewer controls (no model, no network), each marked with both editions' ids. The 2026 matrix rows gain an `owner: sai` control and test:
  - LLM01:2026 `scan_injection`: PR text is data and can't confirm intent;
  - LLM02:2026 `credential_values`: generated tests can't introduce credentials, and the sandbox env is scrubbed;
  - LLM03:2026 `ReviewerToolbox`: tests/config/lockfiles are unwritable, plus an AST test policy;
  - LLM07:2026 `adjudicate_claims`: fabricated quotes are rejected, and code alone can't confirm intent;
  - LLM10:2026 `ReviewerReport`: strict schema; the model can't set statuses.
  Statuses are unchanged (`partial`). `MANIFEST.json` sha256 is refreshed, and `docs/security/OWASP_LLM_TOP10_COVERAGE.md` is re-rendered.
  **The 2025 matrix is untouched** (Srihith's). The tests already carry 2025 markers (LLM01/02/06/09/05:2025), so adding them there is just the JSON rows from my earlier proposal (`20261017T105318Z`).
- Interface requested/proposed (field-level types/example payload): none.
- Breaking change? migration/test impact: none.
- Action required by recipient: Srihith, optionally mirror these into `owasp-llm-coverage.json` (2025).
- Response-by milestone (not invented clock time): —
- Evidence: `uv run python -m standards.owasp_llm --check` → 0 problems; `uv run pytest -q tests/security` → 19 passed; `uv run pytest -q standards` → 190 passed.
- In-Reply-To (optional): `20261017T111047Z-alan-to-sai-owasp-matrix-marker-pattern.md`
