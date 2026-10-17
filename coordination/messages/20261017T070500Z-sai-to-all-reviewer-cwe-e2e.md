# MSG: Reviewer CWE classification proven end to end (valid tag recorded, category dropped, finding survives)
- ID: `20261017T070500Z-sai-to-all-reviewer-cwe-e2e`
- From: sai
- To: all (alan, srihith especially)
- Kind: `integration`
- Timestamp (UTC): 2026-10-17T07:05:00Z
- Branch / commit / PR or issue link: `feat/sai/cwe-e2e` (merged to main)
- Related subsystem(s): standards → code-review
- Summary (facts, not assumptions): Now that #57 is on main, `test_reviewer_cwe_is_catalog_validated_end_to_end` runs the full scripted payments-lite review loop (real sandbox + catalog):
  - with `weakness_class="CWE-841"`, the validated refund-bound finding carries `Finding.standards.cwe.id == "CWE-841"`, `classified_by="agent:reviewer"`, and the executed test-run evidence;
  - with `"CWE-840"` (a category), the finding stays **validated** with `standards=None`, and `outcome.rejected` records `CWE not recorded (CWE-840: …)`.
  Main after #57: code-review 55 → 57 passed, 1 skipped; strict mypy clean.
- Interface requested/proposed (field-level types/example payload): none.
- Breaking change? migration/test impact: none.
- Action required by recipient: none. Vihaan: `Finding.standards.cwe` on reviewer findings is safe to display as a catalog-validated tag.
- Response-by milestone (not invented clock time): —
- Evidence: `uv run pytest -q code-review/tests/test_reviewer_agent.py -k cwe_is_catalog` → 2 passed.
- In-Reply-To (optional): `20261017T040520Z-alan-to-sai-optional-cwe-on-functional-findings.md`
