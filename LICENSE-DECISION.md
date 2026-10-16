# License decision — PENDING

**No license has been chosen.** Until one is, the code is "all rights reserved" by
default: others may view it if the repo is ever made public, but have no right to
use, modify, or redistribute it. The repository is private.

## Why it is deferred

The project may become a commercial startup. The license choice affects
fundraising, contributor rights, competitor reuse, and open-source community
building. It should be made deliberately by the founding team, ideally with
legal input — not defaulted by a setup script.

## Options

| Option | Pros | Cons | Fits if… |
|---|---|---|---|
| **Proprietary / no license** (current) | Maximum control | No outside contributions; weaker build-in-public story | We stay closed-source |
| **Apache-2.0** | Permissive, patent grant, enterprise-friendly | Competitors can take and commercialize | We want max adoption, monetize hosting/services |
| **MIT** | Simplest permissive | No patent grant | Same as Apache, smaller concerns |
| **AGPL-3.0** | Network-copyleft discourages closed SaaS forks | Some enterprises ban AGPL | We want open source but protect against SaaS clones |
| **BSL / FSL (source-available, delayed open)** | Public code, commercial protection, converts to OSS later | Not OSI open source; community skepticism | We want build-in-public with commercial protection |
| **Open core** (e.g. Apache core + proprietary enterprise) | Community + business | Boundary maintenance cost | Clear split between core and enterprise features |

## Also needed regardless of choice

- A **Contributor License Agreement or DCO** policy before accepting outside PRs.
- License review of dependencies, especially security tooling (e.g. rule-pack
  licenses for static analyzers) and any model checkpoints.
- A policy on whether `examples/` vulnerable apps may be published.

## Decision record

| Field | Value |
|---|---|
| Status | Pending |
| Owner | UNASSIGNED |
| Decide by | Before the repo is made public or outside contributions are accepted |
| Tracking task | `DOCS-003` |
