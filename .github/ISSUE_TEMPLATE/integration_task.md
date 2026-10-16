---
name: Integration task
about: Connect two subsystems or an external system through a contract
title: "[INTEGRATION] "
labels: ["type:integration"]
---

## Producer → Consumer
<!-- e.g. code-intelligence → security-agents (Scout context pack) -->

## Contract
<!-- shared/ model(s), API endpoint(s), or event type(s). Link docs/12 section. -->

## Integration checkpoint
<!-- Which checkpoint in docs/25_INTEGRATION_STRATEGY.md does this satisfy? -->

## Acceptance criteria
- [ ] Contract test exists on both sides
- [ ] End-to-end path exercised with fixture data
- [ ] Failure behavior defined (timeout, invalid payload, missing data)

## External system (if any)
<!-- Auth method, permissions required (least privilege), rate limits, sandbox/test account -->
