# shared/

> **What exists: nothing yet (Phase 0).** Contracts are specified as docs in
> [docs/12](../docs/12_DATA_MODELS_AND_CONTRACTS.md). Decision:
> [ADR-0004](../docs/decisions/0004-contract-first-shared-models.md).

## Purpose
The single source of truth for every data contract that crosses a subsystem
boundary: Pydantic v2 models, ID types, enums, the error-code catalog, and
generated JSON Schema + TypeScript.

## Responsibilities
- Models listed in docs/12 (tenancy, scope, intelligence, assessment, findings,
  evidence, monitoring, RL, audit).
- Prefixed ULID ID types; error-code enum; `SCHEMA_VERSION` per module.
- Codegen: `shared/generated/jsonschema/` and `shared/generated/ts/` (committed,
  never hand-edited, regenerated in CI — `.gitattributes` marks them generated).

**Must not:** contain subsystem logic, I/O, or imports of other repo packages.

## Interfaces
- Python package `shared` imported by every Python subsystem.
- Generated TS consumed by `frontend/`.
- JSON Schemas used for LLM structured outputs and contract tests.

## Change rules
Contract changes: `contract-change` label, contract-owner review, regenerate in
the same PR, prefer additive changes ([AGENTS.md](../AGENTS.md) §12).

## Dependencies
Pydantic v2 only (+ a ULID library, proposed). Codegen tooling (e.g.
`datamodel-code-generator` / `json-schema-to-typescript`, to decide in CORE-003).

## Planned layout
```
shared/
  shared/ ids.py errors.py tenancy.py scope.py intel.py assessment.py findings.py
          evidence.py monitoring.py rl.py audit.py
  generated/ jsonschema/ ts/
  tests/
```

## First tasks
CORE-001, CORE-003.

## Commands
None yet.
