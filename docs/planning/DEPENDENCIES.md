# Dependencies

Source of truth for task-level dependencies is the "Depends on" column in
[HACKATL_TASKS](HACKATL_TASKS.md); this page visualizes it. If they disagree, fix
this page.

## Task dependency graph (MVP)

```mermaid
flowchart LR
  CORE001[CORE-001 shared models] --> CORE002[CORE-002 backend skeleton]
  CORE001 --> CORE003[CORE-003 codegen]
  CORE001 --> CORE009[CORE-009 artifact store]
  CORE001 --> SEC002[SEC-002 tool registry + scope_guard]
  CORE001 --> INTEL001[INTEL-001 ingestion]
  CORE002 --> CORE004[CORE-004 schema + repo layer]
  CORE003 --> UI001[UI-001 frontend scaffold]
  CORE003 --> TEST002[TEST-002 contract tests]
  CORE004 --> CORE005[CORE-005 OAuth + projects]
  CORE004 --> CORE006[CORE-006 queue + SSE]
  CORE004 --> CORE007[CORE-007 scope + approvals]
  CORE004 --> CORE008[CORE-008 audit]
  SEC002 --> CORE007
  CORE009 --> CORE010[CORE-010 LLM gateway]
  CORE001 --> CORE010
  CORE010 --> SEC001[SEC-001 agent runtime]
  CORE010 --> TEST001[TEST-001 FakeLLM/replay]
  INFRA005[INFRA-005 sandbox images] --> SEC003[SEC-003 sandbox driver]
  SEC002 --> SEC004[SEC-004 probe sandbox runner]
  SEC003 --> SEC004
  DEMO001[DEMO-001 payments-lite] --> SEC004
  SEC004 --> SEC005[SEC-005 check templates]
  INTEL001 --> INTEL002 --> INTEL003[INTEL-003 py symbols]
  INTEL003 --> INTEL004[INTEL-004 graph]
  INTEL003 --> INTEL005[INTEL-005 entry points]
  INTEL004 --> INTEL006[INTEL-006 expectations]
  INTEL005 --> INTEL006
  CORE010 --> INTEL006
  INTEL006 --> INTEL007[INTEL-007 context packs]
  INTEL004 --> INTEL008[INTEL-008 incremental]
  INTEL007 --> REVIEW001 --> REVIEW002 --> REVIEW003
  SEC003 --> REVIEW002
  SEC001 --> SEC006[SEC-006 Scout]
  INTEL007 --> SEC006
  SEC001 --> SEC007[SEC-007 Probe]
  SEC005 --> SEC007
  SEC001 --> SEC008[SEC-008 Trace] & SEC009[SEC-009 Diagnose] & SEC011[SEC-011 Patch] & SEC013[SEC-013 Fortify]
  SEC001 --> SEC010[SEC-010 Verify]
  SEC004 --> SEC010
  CORE006 --> SEC012[SEC-012 orchestrator]
  CORE007 --> SEC012
  SEC001 --> SEC012
  CORE006 --> MON001 --> MON002 --> MON003
  INTEL008 --> MON002
  SEC012 --> MON003
  RL001[RL-001 env] --> RL002 & RL003
  RL002 --> RL004
  RL003 --> RL004 --> RL005
  MON003 --> UI007
  RL005 --> UI007
```

## Critical path (longest chain to the demo)

CORE-001 → CORE-010 → INTEL-006 → INTEL-007 → SEC-006 / REVIEW-001 → … →
SEC-010 → TEST-005 → DEMO-002.

Parallel chains that must merge before TEST-005: sandbox (INFRA-005 → SEC-003 →
SEC-004 → SEC-005), backend (CORE-002 → CORE-004 → CORE-006/007 → SEC-012),
RL (RL-001 → RL-004), UI (UI-001 → UI-003 → UI-004 → UI-006).

## Starting points (no dependencies)

DOCS-002, DOCS-003, DOCS-004, INFRA-005, CORE-001, DEMO-001, RL-001 — plus
INFRA-002 and INFRA-003, whose only dependency (INFRA-001) is done.

## Unblocking strategy

Consumers develop against fixtures produced from the `shared/` models
([25](../25_INTEGRATION_STRATEGY.md)), so e.g. UI-004 can start with fixture
findings before SEC-* agents exist; its `DONE` still requires the real path.
