# Prior art and related work

Status: **reading list with unverified notes**. Details (dates, results,
licenses) must be checked against primary sources before being cited externally
(RQ-012). Listed for design learning only.

## Classification and scoring standards
- **CWE** (MITRE) — weakness taxonomy; we use CWE ids for `Hypothesis.weakness_class`.
- **OWASP Top 10** and **OWASP API Security Top 10** — broken object-level
  authorization is a prominent API risk category and matches our demo's planted
  weakness class.
- **CVSS** (FIRST) — severity scoring; candidate basis for our rubric (RQ-016).

## Static analysis tools (candidates for `static.analyze`, RQ-006)
- Semgrep (rule-based, multi-language), CodeQL (query-based semantic analysis),
  Bandit (Python security linter). Licensing of engines and rule packs differs
  and must be reviewed.

## Code parsing
- Tree-sitter — incremental parsing library with grammars for many languages;
  basis for our indexer.

## Benchmarks for code agents and analyzers
- SWE-bench — repository-level issue resolution benchmark; informs how we judge
  patches by executed tests.
- OWASP Benchmark and NIST SARD/Juliet test suites — labeled test cases for
  evaluating analyzers; candidates for precision measurement.
- Deliberately vulnerable apps (OWASP Juice Shop, DVWA, etc.) — models for our own
  `examples/` targets; we build our own to control licensing and content.

## RL for cyber defense
- Double DQN (van Hasselt, Guez, Silver) — reduces Q-value overestimation;
  our agent's algorithm.
- Gymnasium (Farama Foundation) — environment API we implement.
- Cyber-defense simulation environments such as Microsoft's CyberBattleSim and the
  CybORG / CAGE challenge environments — study for environment design and
  baselines; we deliberately keep our simulator abstract.

## Autonomous security research programs
- DARPA AI Cyber Challenge (AIxCC) — systems that find and fix vulnerabilities
  automatically; relevant to our find → patch → verify loop.

## LLM agents and safety
- Prompt-injection literature and OWASP Top 10 for LLM Applications — inform
  [15](../15_SECURITY_BOUNDARIES.md) §5.
