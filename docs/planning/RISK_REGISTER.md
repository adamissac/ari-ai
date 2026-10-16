# Delivery risk register

Architectural risks: [26](../26_RISKS_AND_TRADEOFFS.md). Owners UNASSIGNED.

| ID | Risk | L | I | Mitigation | Owner |
|---|---|---|---|---|---|
| D-01 | HackATL date/format unknown; plan may not fit | H | H | Confirm (RQ-011); maintain cut order in MVP_SCOPE | UNASSIGNED |
| D-02 | Team size/roles not set | H | H | Fill TEAM_ASSIGNMENTS at Phase 1 kickoff | UNASSIGNED |
| D-03 | Critical path through LLM gateway + expectations is long | M | H | Start CORE-001/CORE-010 first; fixtures for consumers | UNASSIGNED |
| D-04 | Docker sandbox issues on some laptops (Apple silicon, Windows) | M | M | Multi-arch images; demo on one known-good machine | UNASSIGNED |
| D-05 | LLM API outage or rate limit during demo | M | H | Recorded replay with banner; offline video | UNASSIGNED |
| D-06 | Integration happens too late | M | H | Walking skeleton (IC-2) in Phase 1; daily merges | UNASSIGNED |
| D-07 | RL results weak vs threshold baseline | M | M | Report honestly; it is still a valid result | UNASSIGNED |
| D-08 | Scope creep (more languages, more agents' features) | H | M | MVP_SCOPE in/out list; backlog | UNASSIGNED |
| D-09 | Budget overrun on LLM spend during development | M | M | Per-assessment and daily caps; FakeLLM by default | UNASSIGNED |
