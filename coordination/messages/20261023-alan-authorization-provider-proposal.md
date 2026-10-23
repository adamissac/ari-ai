# Alan to shared/backend/RL owners: research authorization provider proposal

Owner-authorized RL-CMDP-006, branch feat/alan/authorization-context-provider.
The user's explicit source-of-truth decision is payments-lite plus existing trusted
lab delegation records; no external authorization service exists. Proposed version
0.1.0 is documented in docs/research/authorization-context/README.md before adapter
implementation. Four classifications; explicit fixture clock domain/revision;
unknown abstains; ControlGrant remains separate. Future causal observation rules
exclude hidden labels, future windows and retrospective permission backfills.

The current interface stays internal behind the research adapter, reusing the
existing kernel. Cross-system publication requires canonical shared models/codegen
and consumer agreement; this PR does not expose a new network contract. Alan is
interim shared approver and authorized this research direction. No consumer should
integrate this internal prototype as a production permission service.
