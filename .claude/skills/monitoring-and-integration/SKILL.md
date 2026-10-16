---
name: monitoring-and-integration
description: Build trustworthy GitHub webhook ingestion, durable assessment triggers, scoped background processing and observable state. Use for Srihith integration.
---

# monitoring-and-integration


1. Verify GitHub webhook signature over original raw body with constant-time comparison; size bound and delivery ID dedupe before processing. Never trust repo URL/target from unverified payload.
2. Persist event, respond quickly and enqueue idempotent job in durable Postgres; demonstrate restart/retry and no duplicate side effects. Runtime signals are not automatically confirmed attacks.
3. Normalize changed SHA/range, ask intelligence for diff impact, prioritize affected expectations/tests/findings; orchestrator runs only within active AuthorizedScope and budget.
4. Persist audit/assessment state transitions with error codes, model usage and artifact refs; SSE timeline reconnect should not fabricate lost progress.
5. Treat worker uptime/deploy as prerequisite for claiming 24/7 monitoring. Signed test event != real production telemetry.
6. Link typed contracts and real assessment records to frontend; unit/integration test invalid signatures, duplicate events, missing approval, process restarts and live local API consumption.
