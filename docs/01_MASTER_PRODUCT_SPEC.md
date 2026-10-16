# 01 — Master product specification

Status: **specified** (Phase 0). Owner: UNASSIGNED.

## 1. Vision

An AI engineering team that understands your software, makes sure it works
correctly, challenges its security, repairs verified problems, and keeps defending
it after deployment.

## 2. The problem

Teams ship faster than they can review. Static analyzers produce long lists of
low-confidence warnings with no notion of what the code is *meant* to do; LLM
code reviewers produce plausible-sounding comments with no proof; penetration
tests are periodic and expensive; runtime monitoring has no link back to the
code that changed. These tools do not share context, so every handoff loses
information and every claim must be re-checked by a human. See
[02 Problem and users](02_PROBLEM_AND_USERS.md).

## 3. The product hypothesis

The value is **not** "we use AI" or "we have agents". It is:

> A shared, version-aware intelligence layer that connects intended behavior,
> functional verification, adversarial validation, evidence-backed remediation,
> and continuous monitoring.

If that layer exists, a single expectation such as *"a customer can only read
their own payments"* can drive a functional test (P1), judge whether an
authorization weakness is real (P2), and explain why a runtime anomaly matters
(P3). This is a hypothesis to validate, recorded as RQ-001 in
[research/RESEARCH_QUESTIONS](research/RESEARCH_QUESTIONS.md).

## 4. The three pillars

### Pillar 1 — Code intelligence, review & repair
*Does the software actually work the way it is supposed to?*
- Index a repository at a specific commit: files, symbols, call graph,
  dependencies, entry points (HTTP routes, CLI commands, jobs).
- Derive **behavioral expectations** from tests, docs, type signatures, auth
  decorators, and naming, each with provenance and a confidence level.
- Review code against those expectations; generate behavioral tests; produce
  **candidate** repairs in isolated worktrees.
- Specs: [05](05_CODE_INTELLIGENCE_ENGINE.md), [06](06_CODE_REVIEW_AND_REPAIR.md).

### Pillar 2 — Seven-agent cybersecurity team
*Even if it works, can an attacker exploit it?*
- Seven narrowly-scoped runtime agents (Scout, Probe, Trace, Diagnose, Patch,
  Fortify, Verify) coordinated by a deterministic state machine.
- Testing happens only against targets in an approved **AuthorizedScope**, inside
  network-restricted sandboxes, with non-destructive checks.
- Specs: [07](07_SEVEN_AGENT_CYBERTEAM.md), [08](08_AGENT_ORCHESTRATION.md), [agents/](agents/AGENT_CONTRACT.md).

### Pillar 3 — Continuous monitoring & RL defense
*As the software changes and runs, how do we keep it secure?*
- Ingest repository events (push, PR) and runtime signals; decide which
  expectations and findings a change affects; request targeted re-assessment.
- An offline reinforcement-learning agent (Double DQN in a simulated
  environment) learns defensive response policies and outputs
  **recommendations** — it never acts on real systems.
- Specs: [09](09_RL_DEFENSE_SYSTEM.md), [10](10_CONTINUOUS_MONITORING.md), [17](17_RL_EVALUATION_PROTOCOL.md).

## 5. The closed loop

```
UNDERSTAND → REVIEW → TEST → ATTACK SAFELY → DIAGNOSE → REPAIR → VERIFY → MONITOR → LEARN → REPEAT
```

| Step | Produced by | Output object ([12](12_DATA_MODELS_AND_CONTRACTS.md)) |
|---|---|---|
| Understand | code-intelligence | `Snapshot`, `Symbol`, `BehavioralExpectation` |
| Review | code-review | `Finding` (kind=functional) |
| Test | code-review | `GeneratedTest`, `TestRun` |
| Attack safely | Scout → Probe → Trace | `Hypothesis`, `ValidationResult`, `AttackPath` |
| Diagnose | Diagnose | `RootCause`, `RemediationPlan` |
| Repair | Patch (or code-review repair) | `PatchCandidate` |
| Verify | Verify | `VerificationResult` |
| Monitor | monitoring | `MonitoringEvent`, `ReassessmentRequest` |
| Learn | rl-defense, intelligence layer | `DefenseRecommendation`, regression tests added to the suite |

## 6. Core principles

1. **Evidence over assertion.** A finding is only "validated" when an executed
   test or sandboxed check produced evidence. A fix is only "verified" when Verify
   re-ran the failing check and the functional tests in a fresh sandbox.
2. **Safety is code.** Scope checks, sandbox limits, budgets and approval gates
   are deterministic and enforced outside the model.
3. **Humans approve consequential actions.** Registering scope, opening a PR,
   and any change to a real system require a human. The platform never merges or
   deploys.
4. **Honest UX.** Every displayed claim shows its status (hypothesis, validated,
   verified, rejected) and links to evidence.
5. **Version awareness.** Every fact is tied to a commit; stale facts are marked.

## 7. Users

Primary: small product engineering teams without a dedicated security team.
Secondary: security engineers who want triaged, reproducible findings; engineering
leads who want assurance that changes did not regress behavior or security.
Details in [02](02_PROBLEM_AND_USERS.md).

## 8. Scope for HackATL (MVP)

One complete loop on a deliberately vulnerable demo target we own
(`examples/`), for Python web services first. See
[planning/MVP_SCOPE](planning/MVP_SCOPE.md). Explicitly **out** of MVP: multiple
languages beyond Python (JS/TS is stretch), live production monitoring of third-
party systems, auto-merge, any real-infrastructure RL action, multi-tenant SaaS.

## 9. Non-goals (permanent)

- Testing systems without the owner's authorization.
- Autonomous deployment or merging of code.
- Generating weaponized exploits for third-party software.
- Replacing human security judgment for production risk acceptance.

## 10. Success criteria

| Horizon | Criterion |
|---|---|
| HackATL | On the demo target, the loop finds ≥ 1 functional bug and ≥ 1 authorization weakness, validates them with executed evidence, produces patches that Verify accepts, and a push that reintroduces the bug triggers re-assessment. All claims traceable in the UI. |
| HackATL (RL) | DDQN beats random and no-op baselines and is compared honestly against the rule-based baseline in the simulator under [17](17_RL_EVALUATION_PROTOCOL.md). |
| Post-hackathon | Precision of validated findings on a labeled benchmark ([research/EVALUATION_DATASETS](research/EVALUATION_DATASETS.md)); design-partner feedback. |

## 11. Related

Requirements: [03](03_PRODUCT_REQUIREMENTS.md). Risks: [26](26_RISKS_AND_TRADEOFFS.md).
Glossary: [22](22_GLOSSARY.md).
