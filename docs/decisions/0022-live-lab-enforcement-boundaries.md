# ADR-0022: Boundaries of live policy enforcement in the isolated lab (proposed)

- Status: Proposed (owner review: Alan, RL lane)
- Date: 2026-10-23
- Context: `rl_defense.live` closes a loop between a trained policy and a gateway that
  enforces controls (`block_principal*`, node `isolate`/`rate_limit`) against the owned
  payments-lite lab. ADR-0008 says platform inference produces recommendations only;
  issue #317 recorded that nothing documented how the lab loop differs. This ADR records
  the boundary and the known honesty gaps. It changes no behaviour.

## Decision

1. **Where enforcement is permitted.** Only the live lab loop (`rl-defense/rl_defense/live`)
   enforces, only against its isolated demo app, and only the controls in the lab layout
   (`live_v2`/`live_v3`). Platform inference (`PolicyRunner`, the API) stays
   recommendations-only (ADR-0008 unchanged). Nothing here targets production or third-party
   systems.
2. **No auto-apply of learned actions outside the lab.** A learned policy never changes a
   customer system. Owned-test enforcement for customers is the separate, deterministic
   Live Defense control gate (ADR-0020), which a policy cannot bypass.
3. **Lab numbers are lab evidence.** They come from a scripted adversary and a hand-written
   gateway; they do not establish real-world effectiveness (RQ-005).

## Known gaps (documented, not fixed here)

These affect how lab results may be described. Fixing them changes masks or dynamics that
preregistered studies and trained checkpoints depend on, so each needs the RL owner's call:

- `escalate_to_human` spends the escalation budget and starts a timer but has no effect on
  gateway state or measured outcomes (unlike `DefenseSimEnv`). Options: mask it in the live
  layouts, or give it a real completion effect.
- Node actions on nodes the gateway cannot influence (`db`, `auth`, `gateway`) stay selectable;
  they are valid in the mask but act only on timers. Option: mask them from topology.
- `LiveRecord.is_attack` is the traffic generator's intent, used for metrics only, never
  for telemetry; `request_reassessment` is a scripted severity drop, not a re-test.
- `LiveTransition` realizes the proposed experience schema locally (`live/contracts.py`);
  promoting it to `shared/` is deferred.

## Consequences

Reports built on the live loop must say "isolated lab" and must not claim the escalation or
unenforceable node actions had an effect. Status of each gap is tracked on #317.
