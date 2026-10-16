# Research questions

Status: `OPEN` | `IN_RESEARCH` | `ANSWERED` (link evidence) | `DROPPED`.
Owners UNASSIGNED. Add new questions at the bottom with the next ID.

| ID | Question | Why it matters / unblocks | Status | Owner |
|---|---|---|---|---|
| RQ-001 | Does a shared expectation layer measurably improve finding precision and fix acceptance compared with running the same components without shared expectations? | Core product hypothesis ([01](../01_MASTER_PRODUCT_SPEC.md) §3) | OPEN | UNASSIGNED |
| RQ-002 | What precision/recall do our expectation extractors (tests, docstrings, conventions, LLM inference) achieve on labeled fixtures? | R-01; INTEL-006 design; confidence calibration | OPEN | UNASSIGNED |
| RQ-003 | How accurate is static call resolution on typical FastAPI/Flask code; what share of edges is `unresolved`? | R-11; Trace/Scout quality | OPEN | UNASSIGNED |
| RQ-004 | Is graph + BM25 retrieval recall sufficient for agents' context needs, or do we need embeddings? | ADR-0010 revisit; INTEL-103 | OPEN | UNASSIGNED |
| RQ-005 | Do policies trained in `DefenseSimEnv` transfer to replayed real monitoring signals in any meaningful way? | Limits of RL claims; RL-102 | OPEN | UNASSIGNED |
| RQ-006 | Which pinned open-source static analyzer(s) back `static.analyze`, and are their licenses and rule-pack licenses compatible with our future license? | TOOL_REGISTRY; LICENSE-DECISION | OPEN | UNASSIGNED |
| RQ-007 | How do we host sandboxes safely without paid infrastructure (or what is the minimum approved paid option)? | Hosted demo/staging; INFRA-102 | OPEN | UNASSIGNED |
| RQ-008 | Python tooling: `uv` vs Poetry vs pip-tools for a multi-package monorepo; pnpm vs npm for frontend | CORE-002, UI-001 setup | OPEN | UNASSIGNED |
| RQ-009 | How are a target repo's dependencies installed for sandboxed test runs when the run itself has no network (separate build step with network to a package mirror only? pre-built images?) | SEC-003, INFRA-005, REVIEW-002; NFR-02 | OPEN | UNASSIGNED |
| RQ-010 | Do target users (personas in [02](../02_PROBLEM_AND_USERS.md)) value evidence-gated findings enough to accept a scope + approval workflow? | Assumptions A-1…A-3; PROD-101 | OPEN | UNASSIGNED |
| RQ-011 | HackATL date, duration, demo format, judging criteria, and rules on pre-built code | Roadmap timing; demo length; D-01 | OPEN | UNASSIGNED |
| RQ-012 | Verify the competitive landscape claims in [21](../21_COMPETITIVE_LANDSCAPE.md) against current vendor documentation | Pitch accuracy | OPEN | UNASSIGNED |
| RQ-013 | Data retention policy for audit events and transcripts (legal/compliance input) | [architecture/data-flow-and-storage](../architecture/data-flow-and-storage.md) | OPEN | UNASSIGNED |
| RQ-014 | Team size, members and role assignments | TEAM_ASSIGNMENTS, CODEOWNERS | OPEN | UNASSIGNED |
| RQ-015 | Replace the custom Code of Conduct with Contributor Covenant v2.1 verbatim? | [CODE_OF_CONDUCT](../../CODE_OF_CONDUCT.md) | OPEN | UNASSIGNED |
| RQ-016 | Which severity rubric do we adopt (CVSS v4 base metrics subset vs. custom factors) and how do we explain it in the UI? | SEC-008; UX trust | OPEN | UNASSIGNED |
| RQ-017 | How do we generate realistic synthetic fixture identities/data for target sandboxes across different apps (beyond payments-lite)? | SEC-005 generalization | OPEN | UNASSIGNED |
| RQ-018 | Which model (default vs fast) per agent gives acceptable quality at our budget caps? | Cost control; AGENT_MODEL_OVERRIDES defaults | OPEN | UNASSIGNED |
