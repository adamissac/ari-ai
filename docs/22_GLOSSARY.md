# 22 — Glossary

| Term | Meaning in this project |
|---|---|
| **AgentRun** | One execution of one agent step, with model id, usage and status. |
| **Approval** | A human decision recorded via the API (scope, remediation, PR). |
| **Assessment** | One orchestrated run of the loop for a project snapshot under a scope. |
| **Attack path** | Trace's ordered steps from entry point to impact; each step marked verified or hypothesis. |
| **AuthorizedScope** | Approved, expiring record of what the platform may test. MVP: sandbox builds of the connected repo only. |
| **Baseline (RL)** | `random`, `noop`, `threshold_rules` policies every RL result is compared to. |
| **Behavioral expectation** | Falsifiable statement of intended behavior with provenance and confidence. |
| **Check template** | Versioned, reviewed, non-destructive validation procedure Probe may run. |
| **Context pack** | Bounded, provenance-tagged retrieval result given to an agent. |
| **Development agent** | A coding assistant (Claude Code, Codex…) building this repo. Not a product feature. |
| **DDQN** | Double Deep Q-Network: online net selects action, target net evaluates it. |
| **Evidence / EvidenceRef** | Pointer to code span, test run, sandbox run, artifact or human input supporting a claim. |
| **Finding** | Tracked problem (functional or security) with a status lifecycle. |
| **Freshness** | Whether a fact is valid for a given snapshot. |
| **Gate** | Deterministic check in the orchestrator (scope, approval, budget, kill switch). |
| **Hypothesis** | Suspected weakness not yet validated. Never presented as a finding. |
| **ImpactSet** | Symbols/expectations/findings/tests affected by a diff. |
| **Implemented / specified / proposed / hypothesis** | Required status words when describing anything. |
| **LLM gateway** | The only path to model calls; enforces budget, logging, redaction, schema validation. |
| **Orchestrator** | Deterministic state machine that sequences agents and enforces gates. |
| **PatchCandidate** | Diff produced in an isolated worktree; not merged, not trusted until verified. |
| **Pillar** | P1 intelligence/review/repair, P2 security agents, P3 monitoring/RL. |
| **Regression test** | Test created from a verified fix; re-run on later changes. |
| **Runtime agent** | One of the seven product agents: Scout, Probe, Trace, Diagnose, Patch, Fortify, Verify. |
| **Sandbox** | Ephemeral, limited, network-restricted container for any untrusted execution. |
| **Snapshot** | Indexed state of a repo at a commit SHA. |
| **Unified Intelligence Layer** | Shared, version-keyed fact store all subsystems use ([11](11_SHARED_CONTEXT_AND_MEMORY.md)). |
| **Validated** | Hypothesis confirmed by an executed check with evidence. |
| **Verified** | Patch accepted by Verify after all checks pass in a fresh sandbox. |
| **Worktree** | Isolated git working copy where Patch/repair writes code. |
