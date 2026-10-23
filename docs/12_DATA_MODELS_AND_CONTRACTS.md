# 12 — Data models and contracts

Status: **specified** (documentation only; no Pydantic models exist yet).
Decision: [ADR-0004](decisions/0004-contract-first-shared-models.md).
Home once implemented: `shared/` (source of truth: Pydantic v2) →
`shared/generated/` (JSON Schema + TypeScript, generated, never hand-edited).

## Conventions

- **IDs:** ULID with a type prefix, e.g. `prj_01J…`. Prefixes below.
- **Timestamps:** UTC, ISO-8601, field names end in `_at`.
- **Enums:** lowercase snake_case strings.
- **Versioning:** each model module has `SCHEMA_VERSION`; breaking change → bump
  and `contract-change` label ([24](24_DEVELOPMENT_STANDARDS.md)).
- **Extensibility:** `model_config = ConfigDict(extra="forbid")` for all
  inbound/LLM-output models; unknown fields are errors.
- **Large content** is never inline; use `artifact_uri` + `sha256`.

| Prefix | Model | Prefix | Model |
|---|---|---|---|
| `org_` | Organization | `fnd_` | Finding |
| `usr_` | User | `hyp_` | Hypothesis |
| `prj_` | Project | `val_` | ValidationResult |
| `rep_` | Repository | `atp_` | AttackPath |
| `snp_` | Snapshot | `rc_` | RootCause |
| `sym_` | Symbol | `pat_` | PatchCandidate |
| `ent_` | EntryPoint | `ver_` | VerificationResult |
| `exp_` | BehavioralExpectation | `hdn_` | HardeningRecommendation |
| `scp_` | AuthorizedScope | `apv_` | Approval |
| `asm_` | Assessment | `aud_` | AuditEvent |
| `run_` | AgentRun | `evt_` | MonitoringEvent |
| `tst_` | TestRun / GeneratedTest | `rec_` | DefenseRecommendation |
| `ctx_` | ContextPack | `ckp_` | RLCheckpoint |
| `app_` | ConnectedApplication | `arv_` | AnalystReview |
| `itk_` | IngestToken | `inc_` | Incident |
| `lpd_` | LivePolicyDecision | `lct_` | LiveControl |
| `cgr_` | ControlGrant | `cch_` | ControlChannel |
| `est_` | EmergencyStop | | |

## Core entities

### Tenancy and access
```
Organization { id, name, created_at }
User { id, github_login, display_name, created_at }
Membership { org_id, user_id, role: owner|member|viewer }
Project { id, org_id, name, created_at, settings: ProjectSettings }
ProjectSettings { default_budget: Budget, monitoring_policy: TriggerPolicy, languages: [str] }
Repository { id, project_id, provider: github, full_name, default_branch, installation_id }
```

### Authorization
```
AuthorizedScope {
  id, project_id, name,
  targets: [ScopeTarget],
  allowed_check_categories: [CheckCategory],  # Probe library ids; V0 aliases accepted
  status: pending|active|expired|revoked,
  requested_by, approved_by?, approved_at?, expires_at,
  notes
}
ScopeTarget {
  kind: sandbox_build,                    # MVP: only targets built from the repo inside our sandbox
  repo_id, build_recipe_ref,              # how to build/run the target container
  exposed_ports: [int]
}
Approval { id, project_id, subject_type: scope|remediation|pr, subject_id,
           decision: approved|declined, decided_by, decided_at, reason? }
```
MVP permits only `sandbox_build` targets. Any other target kind (staging URL,
etc.) is a later, separately reviewed contract change.

`CheckCategory` (canonical Probe library ids, plus published V0 fixture aliases
that canonicalize onto them):

| Canonical (Probe / SEC-005) | V0 fixture alias |
|---|---|
| `access_control.ownership` | `authorization.ownership` |
| `input_validation.bounds` | `input.bounds` |

A scope listing an alias authorizes the matching Probe template. Unknown
category strings are rejected.

### Code intelligence
```
Snapshot { id, repo_id, commit_sha, status: pending|indexing|ready|failed,
           index_version, base_snapshot_id?, stats }
Symbol { id, snapshot_id, kind: module|class|function|method, qualified_name,
         path, start_line, end_line, signature?, decorators: [str], docstring? }
CallEdge { snapshot_id, caller_id, callee_id?, callee_name, resolution: exact|likely|unresolved }
EntryPoint { id, snapshot_id, kind: http_route|cli|job, handler_symbol_id,
             method?, path_template?, auth_dependencies: [str] }
BehavioralExpectation { id, snapshot_id, subject_ref, statement, kind, sources: [EvidenceRef],
                        confidence, origin, status, data_sensitivity?: none|internal|personal|financial }
ContextPack { id, request: ContextPackRequest, chunks: [ContextChunk], token_count }
ContextChunk { provenance: EvidenceRef, content, trust: untrusted }
```

### Assessment and agents
```
Assessment { id, project_id, snapshot_id, scope_id, trigger: manual|monitoring,
             state, budget: Budget, usage: Usage, created_by, created_at, completed_at? }
Budget { max_tokens, max_usd, max_wall_clock_s }
Usage { input_tokens, output_tokens, usd, sandbox_seconds }
AgentRun { id, assessment_id, agent: scout|probe|trace|diagnose|patch|fortify|verify|reviewer,
           step_key, attempt, status: running|succeeded|failed, input_ref, output_ref?,
           model_id, usage, started_at, ended_at, error_code? }
```

### Findings and evidence
```
Finding {
  id, assessment_id, snapshot_id, kind: functional|security,
  title, status, severity?: SeverityAssessment,
  subject_refs: [symbol|entry_point refs],
  expectation_ids: [exp_],
  evidence: [EvidenceRef], history: [StatusChange]
}
Finding.status ∈ hypothesis|validated|refuted|inconclusive|diagnosed|patch_proposed|
                 verified|patch_rejected|unresolved|hardened|accepted_risk|closed|needs_recheck
Hypothesis { id, finding_id, weakness_class (CWE id), rationale, cited_spans: [EvidenceRef],
             expectation_ids, confidence, suggested_check_category }
ValidationResult { id, hypothesis_id, outcome: confirmed|refuted|inconclusive,
                   check_template_id, check_template_version, sandbox_run_id, evidence: [EvidenceRef] }
AttackPath { id, finding_id, steps: [PathStep], preconditions, impact_summary }
PathStep { order, description, symbol_ref?, verified: bool, evidence: [EvidenceRef] }
SeverityAssessment { level: info|low|medium|high|critical, factors: {reachability, privileges_required,
                     data_sensitivity, verified_path}, rationale }
RootCause { id, finding_id, summary, violated_expectation_ids, cause_spans: [EvidenceRef], cause_class }
RemediationPlan { id, finding_id, strategy, constraints: [str], files_expected: [str], test_plan }
PatchCandidate { id, finding_id, attempt, diff_uri, diff_sha256, worktree_ref, files_changed,
                 tests_added: [str], local_test_run_id }
VerificationResult { id, patch_id, verdict: accepted|rejected,
                     checks: [VerificationCheck], sandbox_run_ids, reasons: [str] }
VerificationCheck { name: original_check_now_fails_to_reproduce|functional_suite_passes|
                    generated_tests_pass|no_test_tampering|diff_scope_ok, passed: bool, evidence }
HardeningRecommendation { id, finding_id, category, recommendation, proposed_test_uri?, effort }
```

### Monitoring and RL
```
MonitoringEvent  (see 10)
ImpactSet { base_snapshot_id, head_snapshot_id, symbols, expectations, findings, regression_tests }
ReassessmentRequest { id, project_id, event_ids, scope: full|targeted, targets, status }
DefenseRecommendation { id, project_id, policy_version, action, node, q_margin,
                        observation_ref, caveat: str, created_at }
RLCheckpoint { id, env_id, env_version, config_hash, seed, git_sha, steps, artifact_uri, eval_summary_uri }
```

### Live Defense Phase 4 (owned-test controls)
```
LiveControl { id, project_id, application_id, kind: rate_limit|block_source|increase_logging|escalate,
              target, duration_s, status, origin, checks[], verification?, unresolved,
              environment_label: "OWNED TEST ENVIRONMENT", simulated: false }
ControlGrant { id, project_id, application_id, allowed_kinds, max_duration_s, hourly_budget }
ControlChannel { host: 127.0.0.1, port, path: /live-defense/control }  # HMAC shown once
```
LiveControl statuses are not NIST incident phases. AnalystReview.accept never
transitions a control to executing. `usr_*` in a request body is not identity.

### Audit
```
AuditEvent { id, org_id, project_id?, actor: user|system|agent, actor_id,
             action, subject_type, subject_id, at, details (redacted JSON), prev_hash, hash }
```
Hash-chained (`hash = sha256(prev_hash || canonical_json(event))`) for tamper
evidence; append-only at the DB permission level.

## Error-code catalog (initial)

| Code | Meaning |
|---|---|
| `SCOPE_DENIED` | Target not in active scope or scope inactive |
| `APPROVAL_REQUIRED` | Action needs an approval that does not exist |
| `BUDGET_EXHAUSTED` | Token/USD/time budget reached |
| `SCHEMA_INVALID` | Model or tool output failed validation |
| `SANDBOX_START_FAILED` / `SANDBOX_TIMEOUT` / `SANDBOX_POLICY_VIOLATION` | Sandbox lifecycle |
| `TOOL_NOT_ALLOWED` | Agent requested a tool outside its allowlist |
| `SNAPSHOT_NOT_READY` | Indexing incomplete |
| `WEBHOOK_SIGNATURE_INVALID` | Ingestion auth failure |
| `LLM_UNAVAILABLE` | Upstream model error after retries |
| `CONFLICT_STATE` | Illegal state transition requested |
| `LIVE_CONTROL_DENIED` | Deterministic authorization gate refused an owned-test control |

## Agent I/O schemas

Each agent's input/output is defined in its contract under [agents/](agents/AGENT_CONTRACT.md)
and composed from the models above.

## Contract tests

`tests/contract/` will (1) round-trip each model through JSON, (2) check that
generated JSON Schema matches committed `shared/generated/`, (3) validate
recorded agent outputs against schemas, (4) check API responses against
OpenAPI. See [16](16_TESTING_AND_VERIFICATION.md).
