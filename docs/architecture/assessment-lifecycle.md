# Assessment lifecycle

Status: **specified**. State machine: [08](../08_AGENT_ORCHESTRATION.md).

## Sequence

```mermaid
sequenceDiagram
  autonumber
  participant UI
  participant API
  participant O as Orchestrator
  participant Q as Queue
  participant W as Worker
  participant SB as Sandbox
  UI->>API: POST /projects/{id}/assessments
  API->>O: create (CREATED), audit
  O->>O: SCOPE_CHECK (scope_guard)
  O->>Q: IndexJob
  Q->>W: IndexJob → snapshot READY
  O->>Q: ReviewJob
  W->>SB: run generated behavioral tests (network none)
  W-->>O: functional findings
  O->>Q: AgentStepJob(scout)
  W-->>O: hypotheses
  loop per hypothesis (≤ 10, concurrency 3)
    O->>Q: AgentStepJob(probe)
    W->>SB: check template (target-only, scope-checked)
    W-->>O: ValidationResult
  end
  O->>Q: trace, diagnose (per validated finding)
  O-->>UI: approval.requested (SSE)
  UI->>API: POST /approvals/{id}/decision
  O->>Q: patch (worktree sandbox)
  O->>Q: verify (fresh sandbox)
  O->>Q: fortify
  O-->>UI: assessment.completed
```

## Artifacts per step

| Step | DB records | Artifacts |
|---|---|---|
| Index | Snapshot, Symbol, CallEdge, EntryPoint, Expectation | — |
| Review | Finding(functional), GeneratedTest, TestRun | test files, run logs |
| Scout | AgentRun, Hypothesis, Finding(hypothesis) | transcript (redacted) |
| Probe | AgentRun, ValidationResult | sandbox log, check output |
| Trace | AttackPath, SeverityAssessment | — |
| Diagnose | RootCause, RemediationPlan | — |
| Patch | PatchCandidate | diff, local test logs |
| Verify | VerificationResult | sandbox logs per check |
| Fortify | HardeningRecommendation, RegressionTest | proposed tests |
| Report | Assessment summary | report JSON |

## Concurrency & resumption

Orchestrator transitions run in a DB transaction with `SELECT … FOR UPDATE` on
the assessment row. Jobs are leased; expired leases requeue. On restart, the
orchestrator scans non-terminal assessments and re-emits missing jobs by
`step_key`.
