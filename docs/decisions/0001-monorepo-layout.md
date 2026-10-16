# ADR-0001: Monorepo with one package per subsystem

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-16 |
| Deciders | UNASSIGNED (ratify in DOCS-002) |
| Related | [04](../04_SYSTEM_ARCHITECTURE.md), [24](../24_DEVELOPMENT_STANDARDS.md) |

## Context
Several subsystems (frontend, backend, intelligence, review, agents, RL, monitoring) must share contracts and evolve together during a short hackathon with a small team.

## Decision
One Git repository. Each subsystem is its own top-level directory and (for Python) its own installable package with a public `api.py`. Shared contracts live in `shared/`. Python packages are installed together in one workspace environment for development.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| Monorepo, package per subsystem | Atomic contract changes; one CI; easy discovery | Risk of coupling; needs import rules |
| Polyrepo | Strong boundaries | Contract changes span repos; overhead for a small team |
| Single Python package | Simplest | No boundaries; hard to split later |

## Consequences
- Contract changes and their consumers can land in one PR.
- Import boundaries must be enforced by review now and `import-linter` later (R-10).
- CI must path-filter jobs per subsystem.

## Revisit when
A subsystem needs an independent release cadence or a different team owns it.
