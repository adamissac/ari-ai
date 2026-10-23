# MSG: RL-CMDP-004 owned-fixture response integrity

- From: alan
- To: all
- Kind: implementation / evidence
- Timestamp (UTC): 2026-10-23T14:02:44Z
- Branch: `feat/alan/read-response-integrity`
- Reproduced: authorized pay_a1 request could release a downstream pay_b1 response belonging to another fixture owner with HTTP 200.
- Fix: validate the existing PaymentOut schema, resource and owner; reject malformed/error/framing/duplicate-key responses; emit fresh JSON headers and check freshness after validation.
- Evidence: twenty integration tests pass. No public/shared model or interface change; adapter remains opt-in research only.
- Boundary: current operational ControlGrant authorizes control execution, not payment ownership/delegation. It is not reused as payment authority. No training, promotion, prior comparison rerun, serving registration or customer enforcement.
- Next: CI/review; a real payment authorization-service integration still requires its own canonical producer and consistency agreement.
