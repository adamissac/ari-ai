# Integrating with the control plane (V0)

Owner: Srihith. This is how the other subsystems plug into the backend and worker. The
types come from `shared/` (see `shared/README.md`). The interfaces below are **V0
proposals**. Change requests go through `coordination/messages/` (see
`coordination/CONTRACTS.md`).

## Package layout (import-valid names)

| Dir | Import package | Public API module |
|---|---|---|
| `shared/` | `shared` | `shared.<module>` (+ `shared.registry`) |
| `backend/` | `backend` | `backend.host`, `backend.llm` |
| `monitoring/` | `monitoring` | `monitoring.api` |
| `rl-defense/` | `rl_defense` | `rl_defense.api` (Adam) |
| `security-agents/` | `security_agents` | `security_agents.api` (Alan) |
| `code-intelligence/` | `code_intelligence` | `code_intelligence.api` (Sarosh) |
| `code-review/` | `code_review` | `code_review.api` (Sai) |

Each package has its own `pyproject.toml`. The root `pyproject.toml` is a uv workspace.
Add your directory to `[tool.uv.workspace].members` in your own PR. Add `"hackatl-shared"`
as a dependency with `[tool.uv.sources] hackatl-shared = { workspace = true }`.

## Alan — security-agents orchestrator → `AssessmentHost`

The worker loads `ORCHESTRATOR_FACTORY` (default `security_agents.api:build_orchestrator`).
The factory returns an object with:

```python
class Orchestrator(Protocol):
    def run(self, host: backend.host.AssessmentHost) -> None: ...
```

* `run` is called with the assessment in `SCOPE_CHECK` after the backend scope gate passes.
  It is called again in `AWAITING_APPROVAL` after a human approves or declines a remediation
  approval. Return either in a terminal state or in `AWAITING_APPROVAL`. Anything else is
  failed as `CONFLICT_STATE`.
* `host.transition(state)` only allows legal transitions. It re-checks the active scope.
  `REMEDIATION` requires an approved `remediation` approval.
* `host.start_agent_run(agent, step_key, provider_mode=, model_id=, prompt_version=, input_payload=)`
  and `host.finish_agent_run(run_id, status, usage=, tool_calls=, output=, transcript=, error=)`
  persist an `AgentRun` and stream `agent_run.*` SSE events. Transcripts and outputs go to
  the artifact store, not into the DB row.
* `host.llm()` returns an `LLMGateway`. It is bound to the assessment budget, the usage
  ledger and cancellation. `gateway.run_tool_loop(agent=, system=, user_content=,
  tools=[Tool(...)], output_model=YourPydanticModel)` runs a bounded multi-turn Claude
  tool loop:
  * only the tools you pass can run; any other name is denied with `TOOL_NOT_ALLOWED`;
  * the final result is validated against `output_model`;
  * every call is charged to the assessment.

  Tools are where you enforce per-agent permissions (e.g. Probe's sandbox driver).
* Findings chain: `host.record_finding(Finding)`, `host.record(finding_id,
  Hypothesis | ValidationResult | AttackPath | RootCause | RemediationPlan | HardeningRecommendation)`,
  `host.record_patch(PatchCandidate)`, `host.record_verification(VerificationResult)`.
  Verification is rejected unless it was produced by a `verify` AgentRun that is not the
  patch-producing run.
* Approvals: `host.request_approval(ApprovalSubject.remediation, finding_id, reason)`.
* `host.store_text / store_json` return an `ArtifactRef` for `EvidenceRef(artifact_id, sha256)`.
* Errors: raise or let propagate `HostError` / `LLMError`. The worker maps them to
  `FAILED` / `CANCELLED` / `BUDGET_EXHAUSTED`, keeping the error code.

`backend/tests/reference_orchestrator.py` is a **test double**. It shows every call above
end to end (`test_e2e_host.py`). It is not the product orchestrator.

## Sai — code reviewer

Run as the `reviewer` agent in `FUNCTIONAL_REVIEW`, using the same host and gateway, either
called by Alan's orchestrator or exposed as `code_review.api.review(host, ReviewRequest) ->
ReviewResult`. Functional findings use `Finding.kind = functional`. Generated tests and
patches are stored as artifacts. Verify adjudicates.

## Sarosh — code intelligence

`CODE_INTELLIGENCE_FACTORY` (default `code_intelligence.api:build_service`) returns a
service with:

```python
def index_snapshot(self, snapshot: shared.intelligence.Snapshot, repo_full_name: str) -> Snapshot
def affected_by_diff(self, repo_id: str, base_sha: str | None, head_sha: str) -> shared.intelligence.ImpactSet
```

`POST /api/v1/repositories/{id}/snapshots` enqueues `index_snapshot`. Monitoring calls
`affected_by_diff` for every push and pull request. It must return `head_sha`/`repo_id`
unchanged, or the result is rejected. Until it exists, monitoring degrades to
`ImpactSet.resolution = path_only` and says so in the event's `status_reason`.

## Adam — RL

Integrated and tested (`backend/tests/test_rl_integration.py`) against
`feat/adam/rl-defense`. Set `RL_CHECKPOINT_PATH` and `RL_TOPOLOGY_PATH`. The worker builds
`PlatformFacts` with `rl_defense.platform_mapping.facts_from_platform` from persisted
security findings. A finding contributes only when `Finding.subject_refs` contains route
strings such as `"POST /payments/{id}/refunds"`. Imported evaluations:
`POST /api/v1/projects/{id}/rl-evaluations` stores `eval_summary.json` verbatim.

## Vihaan — frontend

* Types: `shared/generated/ts/contracts.ts` (generated; never hand-edit). Request DTOs are
  in the same file. OpenAPI: `GET /api/openapi.json`.
* Auth: `POST /api/v1/auth/dev/login {github_login}` (dev only), or GitHub OAuth
  `/api/v1/auth/github/login`. It uses an HttpOnly cookie. Send `X-CSRF-Token` (from
  `/api/v1/me` or the login response) on every POST/PATCH. Use `credentials: "include"`.
* Errors are always `{"error": {code, message, details, request_id}}`.
* Live progress: `GET /api/v1/assessments/{id}/events` (SSE, `id:` = `seq`). Resume with
  `Last-Event-ID`. The stream closes after `assessment.completed` / `assessment.failed`.
  The same records are available as JSON from `GET /api/v1/assessments/{id}/events/log?after=N`.
* Monitoring events carry `simulated: true` for locally signed or replayed deliveries.
  Label those in the UI. Defense recommendations always carry `simulation_derived: true`.
