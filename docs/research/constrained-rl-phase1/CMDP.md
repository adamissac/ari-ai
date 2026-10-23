# Proposed partially observed constrained defense process

Status: **research proposal**, with a measured-objective adapter and baseline evaluator
implemented in Phase1. No constrained neural agent/cost critic/training is implemented.
See [audit](AUDIT.md) for implementation and [action matrix](ACTIONS.md) for capability.

## State, observations and actions

Conceptual latent state x_t contains app/control state, current authorization/grants,
request-process state, timers, rate-limit counter and finite-horizon time. The defender
observes o_t: existing55 live_v3 features plus available-action mask, not hidden attacker
schedule/intent. This is a **partially observed CMDP approximation**; the current55-vector
is not proven Markov. A later state proposal should include operator-visible complete
control durations, identity-aware history and remaining intervention/cost budget.
No hidden future request, generator attack-active bit, scenario name or evaluation
label enters a decision. No observation layout change is made now.

Action a_t is one unchanged integer in0..24, filtered through hard capability and
existing validity masks. Policies see the same restricted mask in the new baseline
check. Context (flagged principal/node set) determines the enforcement target; choosing
an integer is not choosing an arbitrary principal. Future authorization must separately
enforce scope, action permission and approval outside every model. The research
capability whitelist is a profile of a known owned fixture, not an authorization service.

Transition: start with o_t after the previous measured window (or reset warmup), apply
an available action, drive the exogenous traffic window through the owned gateway,
measure outcomes, tick timers, obtain o_(t+1). Preserve both current and next masks.
The lab's next-mask record cannot be relabeled as the historical current mask.

## Separate objective channels and what they measure

Let U_t be attack-labelled requests, K_t the subset with a measured successful foreign
customer read, L_t generator-labelled legitimate requests, and D_t the subset refused
by an active defense control. Counts come from `StepOutcome` and, in new evidence,
retained `RequestRecord`s. Define:

- Threat reward r_t=−|K_t| (count units). Under paired fixed exogenous traffic, improving
  this means fewer successful unauthorized reads. It is not a measured causal count of
  prevented attacks, a severity score or a reward inferred from agent prose.
- Benign cost c_t=|D_t| (count units), including own, delegated and other legitimate
  requests. Full aggregate is historically measurable; own/delegated components remain
  unknown unless actual request records and versioned grants identify them.
- Optional operational cost i_t=1[a_t!=noop]. This is an intervention count, not dollars,
  risk or actual human labor. No new administrative reward is introduced.
- Preserve original scalar reward as `legacy_reward`; never substitute it for either
  separated objective or revise its historical experiment meaning.

Choose finite horizon H=30scored windows, gamma_r=gamma_c=1 for the Phase1 reporting
profile. The harness accepts gamma in(0,1] for explicit descriptive cost discounting;
changed gamma requires new config/manifest. Existing DDQN uses gamma=.99; transferring
it is a new experiment, not a mathematical equivalence. Reset warmup is outside scored
returns but its request/control initialization is pinned. Live termination remains
False and horizon truncation ends this finite-horizon objective. Simulator early-db-
impact termination is a different task and cannot be assigned observed HTTP counts.

## Explicit proposed constraints — no deployment authorization

A later policy objective could be `maximize E[sum r_t] subject to E[sum c_t]<=B` and
`E[sum i_t]<=I`, with per-scenario constraints to avoid trading away quiet/delegated
traffic. B must be fixed in a preregistration in **request-count units** for a specific
traffic profile; it is not automatically the historical85% availability floor. With
random benign volume, a ratio-of-expectations availability constraint needs denominators
and evaluation, not an unexamined substitution into one cost sum. No learned B is set
or tuned in Phase1. Missing c is unknown, never zero or an estimated value called measured.

Implemented heuristic constraint: at most2**new short-block actions per episode**,
validated-finding context required. This is a deterministic baseline intervention cap;
it cannot guarantee cumulative harm, because controls outlive the action and future
legitimate demand is uncertain. No guarantee of85% availability is claimed.

Hard authorization and capability exclusions are checked before choosing/executing
an action and cannot be bought off against return. A learned expected-cost constraint
is statistical and may fail on individual trajectories, distribution shift, measurement
errors or rare attacks. It cannot grant permission, approve a patch, merge a change or
satisfy a production SLA. Seven-agent findings provide context/hypotheses only; independent
executed instrumentation plus confirmed expectations would be required for any future
scenario label. Phase1 does not integrate them as rewards.

## Identifiability and extensions

Existing aggregate logs permit r,c,count ratios and finite-horizon on-policy sums,
without reconstructing the old normalizers. They do not identify request-specific
counterfactual outcomes, grant-version changes, actual revenue harm, latency, attacker
intent outside fixtures or causal attribution among multiple controls. New harness
retains request/grant/config provenance for observed breakdowns, still not the missing
counterfactual. Future independent reward/cost estimators should output separate values,
uncertainty, support status and evidence; unsupported actions are unavailable even if a
critic predicts high reward. No neural estimator or automatic learning consumer exists.
