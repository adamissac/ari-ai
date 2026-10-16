# Cross-system contract coordination

The **schema source of truth is `shared/`**, initially maintained by Srihith, with tests. This file is a negotiation record, *not* a second implementation source. Always read `docs/12_DATA_MODELS_AND_CONTRACTS.md` and the actual `shared/` schemas first.

## Required V0 types

`SnapshotRef(project_id, repo_id, commit_sha, snapshot_id, index_version)`; `EvidenceRef(path, sha, span, symbol, artifact_id, provenance)`; `BehavioralExpectation(id, snapshot_id, source, confidence, status, statement)`; `ContextPack(id, snapshot_ref, chunks[], token_budget, provenance[])`; `ReviewRequest`/`ReviewResult`; `AgentRun`/`AgentStepInput`/`AgentStepResult`; `Finding`/`ValidationResult`/`PatchCandidate`/`VerificationResult`; `AuthorizedScope`/`Approval`; `MonitoringEvent`/`Assessment`; `RLRecommendation`/`RLEvaluation`; `AuditEvent`/`ErrorResponse`.

## Evolution procedure

1. Consumer writes message with field-by-field proposed schema and exact reason.
2. Producer/owner acknowledges with acceptance, counterproposal or versioned alternative.
3. Srihith updates canonical Pydantic model and generated JSON Schema/TS types in PR; impacted owners review.
4. Contract tests run in each consumer. Breaking change: require schema version bump and migration/compatibility plan. No unreviewed unilateral shared model edits.
5. New contract is in force only after agreed PR merges and relevant branches sync.

## Freeze target

Publish V0 early (M0), then minimize field/enum churn. Use adapters rather than divergent parallel definitions if an upstream API is temporarily absent. Every network-facing payload must validate strict schema and reject unsupported enum values. Never persist plaintext secrets in event payloads.
