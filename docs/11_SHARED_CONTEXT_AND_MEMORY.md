# 11 — Shared context and memory (Unified Intelligence Layer)

Status: **specified**. This is the core of the product hypothesis
([01](01_MASTER_PRODUCT_SPEC.md) §3).

## What it is

One store of facts about each project's software, keyed by version, with
provenance, that every subsystem reads from and writes to. Not a chat memory —
a typed knowledge base.

## Keys and provenance

Every fact has:

| Field | Meaning |
|---|---|
| `project_id`, `repo_id`, `snapshot_id` (↔ `commit_sha`) | Version key |
| `producer` | Component + version, e.g. `code-intelligence/0.1.0`, `agent:scout/0.1.0` |
| `created_at` | Timestamp |
| `evidence: EvidenceRef[]` | Pointers to source spans, test runs, sandbox logs, artifacts |
| `confidence` | `high` / `medium` / `low` with rule-based meaning per fact type |
| `carried_from` | Snapshot the fact was carried from, if not re-derived |

### `EvidenceRef`
```
EvidenceRef {
  kind: code_span | test_run | sandbox_run | tool_output | artifact | human_input | external_advisory
  snapshot_id?, path?, start_line?, end_line?, symbol?,
  run_id?, artifact_uri?, sha256?,      # integrity for artifacts
  note?                                  # short, non-authoritative
}
```

## Fact types (layers)

| Layer | Fact types | Writers | Readers |
|---|---|---|---|
| Structure | FileNode, Symbol, ImportEdge, CallEdge, EntryPoint, DependencyManifest | code-intelligence | all |
| Intent | BehavioralExpectation | code-intelligence, users | review, agents, monitoring, RL config |
| Assurance | Finding, Hypothesis, ValidationResult, AttackPath, RootCause | review, agents | UI, monitoring, agents |
| Remediation | PatchCandidate, VerificationResult, HardeningRecommendation, RegressionTest | review, Patch, Verify, Fortify | UI, monitoring |
| Operations | MonitoringEvent, ImpactSet, DefenseRecommendation | monitoring, rl-defense | UI, orchestrator |

## Freshness rules

1. A fact is **current** for snapshot S if it was produced for S or carried to S
   by the incremental indexer after proving its evidence spans and 1-hop call
   neighborhood are unchanged.
2. Otherwise it is **stale** for S and must display as such.
3. Findings are re-checked, not carried: a `verified` finding at S₁ becomes
   `needs_recheck` at S₂ if its affected symbols changed; its regression test is
   the cheap recheck.
4. User-confirmed expectations survive changes in unrelated code but revert to
   `proposed` if their subject's signature or auth dependencies change.

## Memory across assessments

- **Regression tests** from verified fixes are stored as `RegressionTest`
  facts and run in every later assessment of affected code.
- **Refuted hypotheses** are remembered per `(snapshot, subject, hypothesis_class)`
  so Scout does not re-raise them unless the code changed.
- **User decisions** (accepted risk, rejected expectation) are facts with
  `evidence.kind = human_input` and an author.

## How agents get context

Through `ContextPack`s only ([05](05_CODE_INTELLIGENCE_ENGINE.md) §Retrieval):
bounded, provenance-tagged, delimited as untrusted data. Agents never query the
database directly; they call read-only tools (`graph.neighbors`,
`expectations.for_subject`, `findings.for_symbol`) that enforce project scoping.

## Storage

PostgreSQL tables per fact type with `(project_id, snapshot_id)` indexes; edges
in adjacency tables (no graph DB in MVP). Large blobs (diffs, logs) in the
artifact store, referenced by URI + SHA-256. See
[architecture/data-flow-and-storage](architecture/data-flow-and-storage.md).

## What would break the differentiator

- A subsystem keeping its own private index of the repo.
- Findings without expectation links where an expectation exists.
- Facts without snapshot keys.
These are review-blocking issues ([24](24_DEVELOPMENT_STANDARDS.md)).
