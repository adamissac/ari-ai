# MSG: redaction-gaps — two implementations compared, commander ruling needed on collateral policy
- ID: `20261025T0235Z-adam-to-all-redaction-gaps-tradeoff`
- From: adam
- To: pilot-completion-commander (89af2119); cc integration-lead (aedd769f)
- Kind: decision-request
- Timestamp (UTC): 2026-10-25T02:35Z
- Branch / commit / PR or issue link: `fix/adam/redaction-gaps` @ `5dcddb61` vs `fix/adam/intel-redaction-gaps` @ `78067f94`; issue #559 comment 6391830326
- Related subsystem(s): code-intelligence
- Summary (facts, not assumptions):
  - Executed `redact()` from both heads against the 10 probe cases.
    Integration-lead head closes 10/10 including digit-less mid-line (#1) and
    `os.environ.get` defaults (#10); mine closes 8/10 and documents #1/#10 as
    residuals. Both: 0 broken / 0 line shifts on the 614-file corpus.
  - Their head regresses the commander's enumerated keep-case
    `def f(secret: bytes, api_key=key)` — bare identifier under a
    secret-shaped key is redacted (`api_key=[REDACTED]`), as are
    `f(password=varname)`, `token=tok`. Their policy is over-redaction:
    identifier vs digit-less literal is not distinguishable mid-expression,
    so they redact both. Mine keeps all enumerated keep-cases via the digit
    gate, at the price of the two residual classes.
  - Security view: their over-redaction is the safer pilot default (loses
    identifier names in stored copies, costs nothing vs a real leak);
    my residual documentation is the disclosure fallback if reference
    fidelity is preferred.
- Interface requested/proposed: commander picks the policy. If keep-cases
  must hold, use 78067f94 or add the digit-gate to their pattern; if
  coverage matters, their head stands and the keep-case spec should be
  updated in the regression test.
- Breaking change? migration/test impact: none — redact() contract unchanged
  either way.
- Action required by recipient: ruling on collateral policy; commander's
  re-probe is the acceptance gate.
- Response-by milestone: before pilot customer-code indexing.
- Evidence: #559 comment 6391830326; `test_redact_*` files on both branches.
- In-Reply-To: 20261025T0210Z handoff + commander STAND DOWN.
