# tests/

> **What exists: nothing yet (Phase 0).** Strategy: [docs/16](../docs/16_TESTING_AND_VERIFICATION.md).

## Purpose
Cross-subsystem test suites. Per-package unit tests live in each package's own
`tests/`; this directory holds what spans packages.

## Responsibilities
| Suite | Path | Runs |
|---|---|---|
| Contract | `tests/contract/` | every PR |
| Integration (incl. checkpoints IC-1…IC-8) | `tests/integration/` | every PR (Docker) |
| Security-boundary SB-01…SB-12 | `tests/security/` | every PR; release-blocking |
| End-to-end demo (IC-9) | `tests/e2e/` | nightly + manual |
| Live-model evals | `tests/evals/` | manual/scheduled with budget cap |
| Shared fixtures | `tests/fixtures/` (incl. `llm/` recorded responses, webhooks) | — |

Also owns the requirement → test mapping table (each `M` requirement in
[docs/03](../docs/03_PRODUCT_REQUIREMENTS.md) → test IDs), added with the first suite.

**Must not:** replace per-package unit tests; contain real secrets, customer
code or third-party exploit content.

## Interfaces
- FakeLLM and recorded-response replay via the backend LLM gateway's replay mode.
- Docker Compose stack (INFRA-004) for integration and e2e.
- `examples/` targets as fixtures.

## Dependencies
pytest, Docker; Playwright for UI e2e (proposed).

## First tasks
TEST-001, TEST-002, TEST-003, TEST-004, TEST-005.

## Commands
None yet.
