# 16 — Testing and verification

Status: **specified**. Two different things share the word "verification":
(a) how **we** test the platform, and (b) how the **platform** verifies fixes
(Verify agent). This doc covers (a) and the rules (b) must satisfy.

## Test pyramid

| Layer | Location | Runs | LLM? |
|---|---|---|---|
| Unit | `<package>/tests/` | every PR | Fake model only |
| Contract | `tests/contract/` | every PR | No |
| Integration | `tests/integration/` | every PR (Docker available) | Recorded responses |
| Security-boundary | `tests/security/` | every PR | No / recorded |
| End-to-end demo | `tests/e2e/` | nightly + manual (`TEST-005`) | Recorded by default; live opt-in |
| Live-model evals | `tests/evals/` | manual / scheduled with budget cap | Live |
| RL | `rl-defense/tests/` + protocol [17](17_RL_EVALUATION_PROTOCOL.md) | PR (smoke), manual (full) | No |

## Testing LLM-dependent code

- **Fake model**: a deterministic `FakeLLM` returning scripted structured outputs
  keyed by step; used for orchestrator and agent loop logic.
- **Recorded responses**: real responses captured from opt-in runs, redacted,
  stored under `tests/fixtures/llm/<scenario>/`, replayed by the gateway in
  `replay` mode. Re-recording is a deliberate act with a PR note.
- **Schema tests**: every recorded output must validate against the current
  schema; schema changes force re-recording or migration.
- **Never** assert on free-text wording; assert on structured fields and evidence.

## Security-boundary suite (release-blocking)

| ID | Test |
|---|---|
| SB-01 | Probe tool call with a target not in scope → `SCOPE_DENIED`, audited, no container network created |
| SB-02 | Assessment with `pending`/`expired`/`revoked` scope fails at `SCOPE_CHECK` |
| SB-03 | Sandbox in `none` mode cannot resolve or reach any address (attempt from inside fixture) |
| SB-04 | Sandbox in `target-only` mode reaches only the target container |
| SB-05 | Sandbox runs as non-root, read-only rootfs, no Docker socket, limits applied (inspect container config) |
| SB-06 | Agent requesting a tool outside its allowlist → `TOOL_NOT_ALLOWED` |
| SB-07 | Recorded injection fixture (repo comment instructing to skip verification) does not change orchestrator transitions |
| SB-08 | Patch cannot be marked verified without a VerificationResult from a separate run/sandbox |
| SB-09 | Verify rejects a patch that modifies a test encoding a confirmed expectation |
| SB-10 | Webhook with bad signature → 401, no event stored |
| SB-11 | Redactor removes secret patterns from logs/transcripts |
| SB-12 | Revoking scope stops a running sandbox |

## Rules the platform's Verify must satisfy (tested)

A patch is `verified` only if **all** pass, each in a fresh sandbox not used by Patch:
1. The original validation check / failing behavioral test no longer reproduces
   the problem.
2. The project's existing test suite passes (or failures equal the baseline
   failures on the unpatched snapshot — recorded explicitly).
3. Generated tests for the finding pass.
4. No test that encodes a confirmed expectation was modified or deleted.
5. Diff stays within the files allowed by the RemediationPlan (+ new test files).

## Evidence requirements for any "done" claim

- PR descriptions list commands actually run and their results
  ([pull request template](../.github/pull_request_template.md)).
- Benchmarks and metrics come from committed scripts with seeds and configs; no
  hand-entered numbers.

## Coverage targets (initial, revisit after Phase 2)

`shared/` 90% lines, orchestrator & scope guard 95% branches, others 70%.
Coverage is a signal, not the goal; SB suite completeness matters more.

## Requirement coverage

Each `M` requirement in [03](03_PRODUCT_REQUIREMENTS.md) maps to ≥ 1 test ID;
the mapping table lives in `tests/README.md` once tests exist.
