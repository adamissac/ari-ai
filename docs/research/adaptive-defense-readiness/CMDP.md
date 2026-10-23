# Candidate partially observed constrained decision process

Proposed mathematical object: (S,A,P,R,C,gamma). It is not an approved simulator.
S would contain trusted application/control state, resource queues, cooldowns,
budgets and observable event history. The policy sees o_t, a causal projection of
that history, not full S. Markov sufficiency is unproven; call this a partially
observed CMDP approximation. A history encoder must be separately validated.

A is the versioned feasibility-filtered research set described in ACTIONS.md.
P must measure how scoped interventions affect later traffic/service/diagnostic
state. Current HTTP traffic generation is action-independent: controls drop requests
but do not make the adversary change policy or establish a load/queue effect.
R must be attributable security benefit beyond deterministic authorization.
C retains separate owner denial, delegate denial, operational and duration costs.
Gamma is proposed as 1 for a finite, fixed episode; horizon and physical window
size are unset until a real residual task and owner-approved protocol exist.
Historical gamma/reward are not changed. Continuing-task bootstrapping requires
separate review; episode truncation cannot silently become natural termination.

Answers to the eight formulation questions:

1. Potential sequential value: allocate a scarce diagnostic/control budget over
   uncertain bursts with delayed resolution and persistent collateral effects.
   This is a hypothesis; current instrumentation does not demonstrate that task.
2. Node rate limits/isolation and principal blocks alter subsequent forwarded
   outcomes while their timers last, but broad harm and deterministic repair make
   their previous BOLA tradeoff an unsuitable new RL target. Logging/escalation have
   no verified downstream security benefit in this HTTP fixture.
3. Only no adaptive action is supported in the new candidate profile. Existing
   laboratory gateway controls are audited, not imported as effective new actions.
4. Only completed events and context available before cutoff, plus measured control
   ledger/budget state if later instrumented. No generator intent/future schedule.
5. Existing offered traffic stays exogenous. A proposed overload/resource-abuse task
   needs measured offered load, service resource consumption, queues, retries and
   recovery before any action-dependent transition model may be claimed.
6. Keep no-op always feasible, unsupported actions hard-masked, control budgets
   independent of policy, unknown explicit, and compare against a strong rule.
   Preserving legitimate access is an external constraint, not a learned permission.
7. No reliable adaptive prevention attribution under the trusted guard; no actual
   investigation completion, real CPU/queue savings, customer availability SLA,
   financial loss or future attacker adaptation is measured. Do not proxy these
   from non-200 responses, a severity decrease or an agent explanation.
8. Strongest read baseline: trusted exact-resource authorization plus no adaptive
   intervention. When it rejects all modeled unauthorized reads, learning to reject
   the same reads cannot improve that endpoint. A new residual task needs separate
   measured baseline headroom before an algorithm comparison.

No new trainable environment is implemented because P and R for a meaningful
residual adaptive task are unsupported. The pure adapter validates causal input
construction without manufacturing dynamics or returning invented rewards.
