---
name: evidence-based-verification
description: Prove integration claims via real executable tests and artifacts, and distinguish replay, simulation and live behavior. Use during reviews, demos and milestone signoff.
---

# evidence-based-verification


1. For each claim identify required evidence, execute relevant command and capture exit code, output path, commit SHA, run ID and environmental preconditions.
2. Unit, integration, end-to-end and opt-in provider tests are separate tiers. A FakeLLM integration run does not prove actual Claude provider tool-use; one live model request does not prove comprehensive seven-agent workflow.
3. Security pass requires original authorized negative assertion plus normal-owner positive behavior before/after. AI prose is not sufficient.
4. RL pass requires actual training gradients, reloadable checkpoint, baseline comparison on held-out seeds and limitation report; no real-world effectiveness claim.
5. Frontend pass requires real API and correct error states; mock/demo fixtures visibly labeled.
6. Summarize observed results and unresolved conditions; never mark unrun tests as passing.
