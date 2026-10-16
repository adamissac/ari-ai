# 21 — Competitive landscape

Status: **draft, team knowledge only — not yet researched or verified**.
Product categories below are described generically; specific vendor claims must
be checked against current sources before use in a pitch (RQ-012).

| Category | What it does well | Gap we target |
|---|---|---|
| SAST / static analyzers (rule-based) | Fast, deterministic, broad CWE coverage | No notion of intended behavior; high false-positive rates; no proof of exploitability |
| SCA / dependency scanners | Known-vulnerable dependency detection | Reachability and app-specific impact usually limited |
| DAST / web scanners | Black-box runtime testing | Weak on business-logic/authorization flaws; no code-level root cause or fix |
| AI code review bots | Readable PR comments, broad coverage | Assertions without executed evidence; no security validation loop |
| AI coding agents / autofix | Generate patches quickly | Fix correctness judged by the same system; little independent verification |
| Pentesting (human / PTaaS) | Deep, creative, business-logic aware | Periodic, expensive, not tied to each change |
| Runtime security / RASP / CNAPP | Production signals | Weak link back to the code change that caused risk |
| Autonomous/AI pentesting research | Agentic exploitation in labs | Usually not connected to functional intent, repair and continuous change tracking |

## Our position

The combination, not any single capability: **intent-aware** (behavioral
expectations), **evidence-gated** (validated/verified states backed by executed
checks), **closed-loop** (repair + independent verification + regression memory),
and **continuous** (change-driven re-assessment), all on one version-aware layer.

## Honest risks in this framing

- Incumbents can add evidence gating to existing products.
- Expectation extraction quality is unproven (RQ-002).
- The narrow MVP (Python web services) may look small to judges; the demo must
  show the loop's depth, not breadth.
