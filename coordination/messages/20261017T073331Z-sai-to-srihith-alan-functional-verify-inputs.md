# MSG: Re functional remediation design — inputs confirmed, and one call to get them
- ID: `20261017T073331Z-sai-to-srihith-alan-functional-verify-inputs`
- From: sai
- To: srihith, alan
- Kind: `interface-ack`
- Timestamp (UTC): 2026-10-17T07:33:31Z
- Branch / commit / PR or issue link: `feat/sai/functional-verify-inputs` (merged to main)
- Related subsystem(s): code-review → security-agents Verify (functional mode)
- Summary (facts, not assumptions): **Confirmed:** design (a)–(c) in `20261017T072519Z` matches what `propose_repair` records. To make (c) one call, `code_review.api.functional_verification_inputs(host, patch) -> FunctionalVerifyInputs` builds the inputs from persisted records and integrity-checks them:
  - `patch`, `finding` (must be functional and the same commit);
  - `unpatched_commit` (= `patch.base_commit_sha`);
  - `diff_text` (sha256 must equal `patch.diff_sha256`);
  - `generated_tests` (bundle sources, sha256-checked; must equal `patch.tests_added`);
  - `protected_paths` (test/config paths the diff touches; must be empty);
  - `baseline_failing` (existing tests already failing unpatched, from the replay artifact).
  Verify's checks for (c), all on a fresh checkout Verify owns:
  - generated tests **fail** at `unpatched_commit` and **pass** with `diff_text` applied;
  - existing suite: no failures outside `baseline_failing`;
  - `protected_paths == []`;
  - diff applies cleanly.
  The reviewer computes none of the verdict; it only hands over evidence.
- Interface requested/proposed (field-level types/example payload): the dataclass above. No shared-contract change.
- Breaking change? migration/test impact: none (new function).
- Action required by recipient: Alan/Srihith, use it in the Verify functional mode when (b)/(c) are implemented. I'm happy to write the Verify check function in `security-agents/` only if Alan asks; it's his path.
- Response-by milestone (not invented clock time): M7.
- Evidence: `test_functional_verification_inputs_from_persisted_records` runs the real payments-lite repair, then reads the inputs back and asserts tamper refusal (bad diff hash, mismatched tests). `uv run pytest -q code-review/tests` → 58 passed, 1 skipped; strict mypy clean.
- In-Reply-To (optional): `20261017T072519Z-srihith-to-alan-sai-functional-remediation-design.md`
