---
name: build-real-llm-agent
description: Implement or audit a real tool-using Claude agent with distinct role instructions, iterative tool calls, typed evidence and enforced budgets/permissions. Use for reviewer and seven security runtime roles.
---

# build-real-llm-agent


1. Define runtime role instruction separate from *development* subagent configuration; list input schema, role objective, tool allowlist, output schema, budget, stop criteria, and failure outcomes.
2. Wire official Anthropic SDK through central LLM gateway with `claude-opus-5-5` config; implement live message/tool-use round trips: model tool request -> independent authorization check -> tool execution -> model observes tool result -> next decision -> typed artifact. Don't fake tool traces or split one completion into seven.
3. Limit tools in code, not just prompt. Scope any network check to explicit owned sandbox, run untrusted tests in isolated resource-limited container, redact inputs/outputs, handle cancellations/rate limits/invalid JSON.
4. Save each step with unique role + model ID, input/output artifacts, tool invocations, evidence spans, run/budget metadata. Correctness/security verdict comes from executable tests, never the agent's final prose.
5. Unit test permission denials and typed output against FakeLLM; opt-in real provider smoke requires key and authorized fixture. Clearly label synthetic/replay vs live.
6. No production merge/deploy from autonomous agents; candidate patches require human approval and independent verification.
