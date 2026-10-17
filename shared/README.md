# shared/

Canonical cross-subsystem contracts: the single source of truth (ADR-0004). Owner:
**Srihith**. Change procedure: [coordination/CONTRACTS.md](../coordination/CONTRACTS.md).

## What exists

* `shared/` Python package (Pydantic v2, `extra="forbid"`, UTC-only timestamps, prefixed
  IDs, 40-hex commit SHAs, repo-relative paths) — schema version **0.9.0**:
  `tenancy`, `scope`, `intelligence`, `assessment` (+ state machine), `findings`,
  `review`, `monitoring`, `rl`, `audit`, `events` (SSE), `errors`, `evidence`, `api` (DTOs).
* `shared.registry.MODELS` lists every exported model.
* Generated (committed, never hand-edited): `generated/jsonschema/<Model>.json`
  (validation mode, usable for LLM structured output), `generated/contracts.schema.json`
  (bundle), `generated/ts/contracts.ts` (frontend types).
* Labeled V0 example payloads for consumer development: `fixtures/v0/<Model>.json`.

## Commands

```bash
uv run python -m shared.export            # regenerate JSON Schema + TypeScript
uv run python -m shared.examples          # regenerate fixtures
uv run python -m shared.export --check    # CI freshness check
TSC=$(which tsc) uv run pytest shared/tests
```

## Rules

No subsystem logic, I/O or imports of other repo packages. Additive changes preferred;
breaking changes bump `SCHEMA_VERSION` and need acknowledgement from affected owners.

Standards and incident contracts in `shared.standards` and `shared.incident` are additive. `Finding.standards` is the canonical finding classification; IDs/names/versions and complete CVSS scores are deterministically validated against the pinned standards package. The 0.6 series is reserved for intelligence-memory work. `IncidentDetail` is the typed API envelope.
