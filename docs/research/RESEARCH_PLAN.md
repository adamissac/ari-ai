# Research plan

Status: **specified**. Research is time-boxed and must end in a decision, an
ADR, or a task update.

## Before Phase 1 starts (blocking or near-blocking)

| RQ | Method | Time box | Output |
|---|---|---|---|
| RQ-011 | Read HackATL rules; ask organizers | 1 hour | Roadmap dates; demo length in [20](../20_DEMO_SCRIPT.md) |
| RQ-014 | Team meeting | 1 hour | TEAM_ASSIGNMENTS filled |
| RQ-008 | Prototype both setups in a throwaway branch | 2 hours | ADR for tooling |
| RQ-009 | Prototype: build image with deps (network to package index only during build), run tests with `--network none` | 4 hours | Update ADR-0006 / SEC-003 design |

## During Phases 2–4

| RQ | Method | Time box | Output |
|---|---|---|---|
| RQ-002 | Label expectations for payments-lite + 2 small OSS-style fixtures we write; measure extractors | 1 day | Confidence calibration table; INTEL-006 tuning |
| RQ-003 | Count edge resolution on fixtures; spot-check | 0.5 day | Resolution stats in code-intelligence README |
| RQ-004 | For each recorded agent step, check whether needed spans were in the pack | 0.5 day | ADR-0010 confirm or revisit |
| RQ-006 | License review of candidate analyzers | 2 hours | TOOL_REGISTRY entry finalized |
| RQ-016 | Compare CVSS subset vs custom factors on fixtures | 2 hours | SEC-008 rubric |
| RQ-018 | Run recorded scenarios with default vs fast model under budget | 0.5 day | Default overrides |

## After HackATL

RQ-001 (controlled comparison with/without shared expectations on a labeled
benchmark), RQ-005, RQ-007, RQ-010 (design-partner interviews), RQ-012, RQ-013,
RQ-017.

## Rules

- Prototypes live on `research/<RQ-ID>-slug` branches and are not merged as product code.
- Results include method, data, and limitations; no unsupported generalization.
