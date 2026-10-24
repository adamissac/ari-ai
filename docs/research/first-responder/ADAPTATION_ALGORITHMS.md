# Algorithm choice and customer-specific adaptation

**Recommendation now: no learning yet.** Use the actual deterministic Grok orchestrator
as the future reference. Rules and budget-aware scheduling provide reproducible,
auditable decisions with known prerequisites. Planning/model-predictive orchestration
is worth evaluating when tool effects and delays can be estimated reliably; inventing
those effects would invalidate the comparison.

Supervised routing is appropriate if independently reliable expert routing labels
exist and selecting a suitable capability is the task. Contextual bandits fit a
next-agent choice with mostly immediate, attributable outcomes and adequate action
support. Both are simpler than long-horizon RL and should be tested when their data
requirements hold. Neither is ready merely because agent execution logs exist.

Constrained Double DQN is a candidate only if discrete decisions have measured delayed
consequences, action masks/costs are observable, history representation is adequate,
and a faithful training environment plus independent evaluation exist. Existing DDQN
code does not establish those conditions. Reward scalarization cannot replace hard
authorization, disclosure and budget gates. A positive learned policy result must
beat strong conventional baselines within uncertainty and satisfy every safety bound.

## Staged application adaptation proposal

1. Configure trusted architecture/deployed commit, approved telemetry, capability
   allowlists, budgets, analyst destinations/preferences and escalation rules. Keep
   customer source-of-truth authorization and independent deterministic gates.
2. Validate deterministic routing and planning on owned reproducible scenarios;
   calibrate configuration and constrained policy selection before considering weights.
3. With explicitly authorized, provenance-complete expert data, evaluate supervised
   routing or a bandit offline when the task matches; hold out application versions.
4. Consider offline RL only after coverage, reward validity and transition fidelity
   pass review; independently compare against the configured baseline on sealed data.
5. Any later deployment requires a separate product/security decision, shadow
   validation, operational monitoring and revocation/rollback. No uncontrolled online
   exploration against customer infrastructure is permitted by this research.

Not every application needs separate model weights. Configuration and policy selection
are preferred when equivalent. Application architecture, verified findings, historical
incidents and analyst feedback require version/provenance validation; old vulnerability
records are not live attack labels. Obtain explicit authorization before using sensitive
source/telemetry for learning. Define tenant isolation, minimization/redaction, retention,
access controls and deletion before collection; avoid secrets in artifacts or prompts.
No automatic customer fine-tuning pipeline or production integration is implemented.
