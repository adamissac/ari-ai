# 26 — Risks and trade-offs

Status: **specified**. Living register of architectural risks; delivery risks
are in [planning/RISK_REGISTER](planning/RISK_REGISTER.md).

## Architectural risks

| ID | Risk | Likelihood | Impact | Mitigation | Trigger to revisit |
|---|---|---|---|---|---|
| R-01 | Expectation extraction is too noisy, weakening the core hypothesis | M | H | Prefer extracted sources over inferred; user confirmation; measure precision (RQ-002) | Precision < 0.6 on fixtures |
| R-02 | Scout hypotheses mostly refuted → slow, costly runs | M | M | Cap + ranking; remember refuted hypotheses; cheaper model for triage | Validated ratio < 10% |
| R-03 | Worker has host Docker access | H | H | Worker never runs untrusted code; dedicated sandbox host; rootless Docker/gVisor post-MVP | Any third-party repo onboarding |
| R-04 | Prompt injection from repo content influences agents | M | H | Controls in [15](15_SECURITY_BOUNDARIES.md) §5; SB-07 test | Any red-team finding |
| R-05 | Patch passes tests by weakening tests | M | H | Verify rule 4 (no test tampering), diff scope rule | — |
| R-06 | Test suites of target repos are slow/flaky | H | M | Baseline-failure recording; timeouts; targeted test selection | Verify > 8 min |
| R-07 | Simulator too simple for RL claims to mean anything | H | M | Strict claim scoping; protocol [17]; baselines | Before any external claim |
| R-08 | LLM cost overruns | M | M | Budgets, caps, recorded replay for demo | Daily cap hit |
| R-09 | Postgres queue insufficient at scale | L (MVP) | M | Abstract queue interface; ADR-0005 revisit | > 10 workers or > 100 jobs/s |
| R-10 | Monorepo coupling across subsystems | M | M | `api.py` boundaries, import-linter | Cycles detected |
| R-11 | Dynamic Python defeats static call graph | H | M | Resolution confidence; LLM fallback flagged low confidence | Many `unresolved` edges on fixtures |
| R-12 | Model id availability/pricing changes | M | L | Config-driven model id; pricing table dated | Gateway errors |

## Key trade-offs made

| Decision | We chose | Over | Because | Cost |
|---|---|---|---|---|
| Orchestration | Deterministic state machine | LLM planner | Safety, testability, replay | Less flexible; new workflows need code |
| Storage | PostgreSQL for everything | Graph DB + vector DB + Redis | One system to run for MVP | Graph queries hand-written |
| Retrieval | Graph + lexical | Embeddings | No extra infra, explainable | May miss semantic matches |
| Sandbox | Docker hardened | gVisor/Firecracker | Available on laptops | Weaker isolation |
| Targets | Sandbox builds only | Staging URLs | Eliminates unauthorized-target class for MVP | Can't test real deployments yet |
| RL | Offline simulation, recommend only | Online RL on real signals | Safety, reproducibility | Unclear real-world transfer |
| Language | Python first | Multi-language | Depth over breadth | Smaller addressable demo |

## Open questions

Tracked in [research/RESEARCH_QUESTIONS](research/RESEARCH_QUESTIONS.md).
