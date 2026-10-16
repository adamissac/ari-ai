# License decision — PROPRIETARY (interim)

**Decided 2026-10-16: proprietary, all rights reserved** ([LICENSE](LICENSE)).
This is an interim choice made to keep every future option open: moving from
proprietary to any open or source-available license later is easy, while code
released under an open license cannot be taken back. The repository stays private.
The choice of a long-term license is still open and is revisited before the repo is
made public or outside contributions are accepted.

## Why the long-term choice is deferred

The project may become a commercial startup. The license choice affects
fundraising, contributor rights, competitor reuse, and open-source community
building. It should be made deliberately by the founding team, ideally with
legal input — not defaulted by a setup script.

## Options

| Option | Pros | Cons | Fits if… |
|---|---|---|---|
| **Proprietary** (current, interim) | Maximum control | No outside contributions; weaker build-in-public story | We stay closed-source |
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
| Status | Decided (interim): proprietary, all rights reserved |
| Decided on | 2026-10-16 |
| Long-term license | Open — revisit before going public |
| Owner | UNASSIGNED |
| Revisit by | Before the repo is made public or outside contributions are accepted |
| Tracking task | `DOCS-003` |
