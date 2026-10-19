"""The live defense loop: trained DQN ↔ real app, closed end to end.

One :meth:`LiveDefenseLoop.step` does, in order:
  1. apply the chosen permitted action to the gateway's enforced controls,
  2. drive one window of **real** benign + attack traffic through the gateway,
  3. measure the real outcome (compromised cross-tenant reads, blocked benign traffic),
  4. compute a reward from those measured counts,
  5. build the next observation from measured telemetry,
  6. return a :class:`LiveTransition` (replay-buffer-shaped).

The policy is any trained checkpoint, loaded through the existing ``PolicyRunner``.
Nothing here observes hidden state; everything is measured from HTTP outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from rl_defense.envs.config import NODE_NAMES
from rl_defense.envs.defense_sim import ESCALATE_ACTION, NOOP_ACTION, decode_action
from rl_defense.inference import PolicyRunner
from rl_defense.live.adversary import TrafficDriver
from rl_defense.live.contracts import DefenseControls, LiveTransition, StepOutcome
from rl_defense.live.gateway import DefensiveGateway
from rl_defense.live.telemetry import build_facts
from rl_defense.live.topology import RouteTopology, load_topology
from rl_defense.observations import from_platform_facts, mask_from_facts

# payments-lite: the known BOLA lives on the payments node.
DEFAULT_FINDING_SEVERITY = {"gateway": 0.1, "api": 0.3, "auth": 0.2, "payments": 0.8, "db": 0.1}


@dataclass
class LoopConfig:
    horizon: int = 30
    max_monitoring_level: int = 2
    max_escalations: int = 3
    isolate_duration: int = 3
    rate_limit_duration: int = 3
    monitoring_duration: int = 5
    reassessment_delay: int = 4
    escalation_duration: int = 3
    reassessment_severity_after: float = 0.2
    # reward coefficients (applied to measured, normalized counts)
    c_impact: float = 1.0
    c_disrupt: float = 0.5
    c_action: float = 0.02
    c_escalate: float = 0.1


@dataclass
class _Timers:
    isolate: dict[str, int] = field(default_factory=dict)
    rate_limit: dict[str, int] = field(default_factory=dict)
    monitoring: dict[str, int] = field(default_factory=dict)
    reassess: dict[str, int] = field(default_factory=dict)
    escalation: int = 0


class LiveDefenseLoop:
    def __init__(
        self,
        app_factory,
        runner: PolicyRunner,
        *,
        config: LoopConfig | None = None,
        topology: RouteTopology | None = None,
        driver: TrafficDriver | None = None,
    ) -> None:
        self._app_factory = app_factory
        self.runner = runner
        self.config = config or LoopConfig()
        self.topology = topology or load_topology()
        self.driver = driver or TrafficDriver()
        self.controls = DefenseControls()
        self.finding_severity = dict(DEFAULT_FINDING_SEVERITY)
        self._timers = _Timers()
        self._gateway: DefensiveGateway | None = None
        self.step_idx = 0
        self.escalations_used = 0

    # ------------------------------------------------------------------ lifecycle
    def reset(self, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
        if self._gateway is not None:
            self._gateway.close()
        self.controls = DefenseControls()
        self.finding_severity = dict(DEFAULT_FINDING_SEVERITY)
        self._timers = _Timers()
        self.step_idx = 0
        self.escalations_used = 0
        self.driver.reset(seed)
        self._gateway = DefensiveGateway(self._app_factory(), self.topology, self.controls)
        # one warm-up window to establish an initial observation from real traffic
        self.driver.run_window(self._gateway)
        facts = self._facts()
        self._gateway.clear_records()
        return self._obs_mask(facts)

    def close(self) -> None:
        if self._gateway is not None:
            self._gateway.close()
            self._gateway = None

    # ------------------------------------------------------------------ one step
    def step(self, action: int) -> LiveTransition:
        assert self._gateway is not None, "call reset() first"
        obs_before, mask_before = self._obs_mask(self._facts_no_traffic())
        if not mask_before[action]:
            action = NOOP_ACTION
        self._apply_action(action)

        self._gateway.clear_records()
        self.driver.run_window(self._gateway)
        records = list(self._gateway.records)

        attack = [r for r in records if r.is_attack]
        benign = [r for r in records if not r.is_attack]
        compromised = sum(1 for r in attack if r.compromised)
        benign_blocked = sum(1 for r in benign if not r.allowed)

        reward, comps = self._reward(action, compromised, benign_blocked)
        self.step_idx += 1
        self._tick_timers()

        facts_next = self._facts()
        next_obs, next_mask = self._obs_mask(facts_next)
        truncated = self.step_idx >= self.config.horizon

        name, node_idx = decode_action(action)
        outcome = StepOutcome(
            step=self.step_idx,
            action=action,
            action_label=name if node_idx is None else f"{name}:{NODE_NAMES[node_idx]}",
            node=None if node_idx is None else NODE_NAMES[node_idx],
            attack_requests=len(attack),
            compromised_reads=compromised,
            benign_requests=len(benign),
            benign_blocked=benign_blocked,
            reward=reward,
            reward_components=comps,
            terminated=False,
            truncated=truncated,
        )
        return LiveTransition(
            obs=[float(x) for x in obs_before],
            action=int(action),
            reward=float(reward),
            next_obs=[float(x) for x in next_obs],
            done=bool(truncated),
            action_mask=[bool(m) for m in next_mask],
            reward_components=comps,
            outcome=outcome,
        )

    def act(self, obs: np.ndarray, mask: np.ndarray) -> int:
        """The trained policy's greedy, mask-respecting choice."""
        return int(self.runner.agent.greedy_action(obs, mask))

    def run_episode(self, seed: int = 0) -> list[LiveTransition]:
        obs, mask = self.reset(seed)
        transitions: list[LiveTransition] = []
        done = False
        while not done:
            action = self.act(obs, mask)
            t = self.step(action)
            transitions.append(t)
            obs = np.asarray(t.next_obs, dtype=np.float32)
            mask = np.asarray(t.action_mask, dtype=bool)
            done = t.done
        return transitions

    # ------------------------------------------------------------------ internals
    def _reward(self, action: int, compromised: int, benign_blocked: int) -> tuple[float, dict]:
        cfg = self.config
        anorm = max(1, self.driver.attack_per_step)
        bnorm = max(1, self.driver.benign_per_step)
        comps = {
            "compromise": -cfg.c_impact * (compromised / anorm),
            "disruption": -cfg.c_disrupt * (benign_blocked / bnorm),
            "action_cost": -cfg.c_action if action != NOOP_ACTION else 0.0,
            "escalation_cost": -cfg.c_escalate if action == ESCALATE_ACTION else 0.0,
        }
        return float(sum(comps.values())), comps

    def _apply_action(self, action: int) -> None:
        name, node_idx = decode_action(action)
        if name == "noop":
            return
        if name == "escalate_to_human":
            if self.escalations_used < self.config.max_escalations:
                self.escalations_used += 1
                self._timers.escalation = self.config.escalation_duration
            return
        node = NODE_NAMES[node_idx]
        if name == "isolate":
            self.controls.isolated[node] = True
            self._timers.isolate[node] = self.config.isolate_duration
        elif name == "rate_limit":
            self.controls.rate_limited[node] = True
            self._timers.rate_limit[node] = self.config.rate_limit_duration
        elif name == "raise_monitoring":
            cur = self.controls.monitoring_level.get(node, 0)
            self.controls.monitoring_level[node] = min(cur + 1, self.config.max_monitoring_level)
            self._timers.monitoring[node] = self.config.monitoring_duration
        elif name == "request_reassessment":
            self.controls.reassessment_pending[node] = True
            self._timers.reassess[node] = self.config.reassessment_delay

    def _tick_timers(self) -> None:
        for node in list(self._timers.isolate):
            self._timers.isolate[node] -= 1
            if self._timers.isolate[node] <= 0:
                self.controls.isolated[node] = False
                del self._timers.isolate[node]
        for node in list(self._timers.rate_limit):
            self._timers.rate_limit[node] -= 1
            if self._timers.rate_limit[node] <= 0:
                self.controls.rate_limited[node] = False
                del self._timers.rate_limit[node]
        for node in list(self._timers.monitoring):
            self._timers.monitoring[node] -= 1
            if self._timers.monitoring[node] <= 0:
                self.controls.monitoring_level[node] = 0
                del self._timers.monitoring[node]
        for node in list(self._timers.reassess):
            self._timers.reassess[node] -= 1
            if self._timers.reassess[node] <= 0:
                # reassessment landed: the finding is remediated → severity drops.
                self.finding_severity[node] = min(
                    self.finding_severity.get(node, 0.0), self.config.reassessment_severity_after
                )
                self.controls.reassessment_pending[node] = False
                del self._timers.reassess[node]
        if self._timers.escalation > 0:
            self._timers.escalation -= 1

    def _facts(self):
        return build_facts(
            self._gateway.records,
            self.controls,
            self.topology,
            finding_severity=self.finding_severity,
            step=self.step_idx,
            horizon=self.config.horizon,
            escalations_used=self.escalations_used,
            max_escalations=self.config.max_escalations,
            escalation_pending=self._timers.escalation > 0,
            max_monitoring_level=self.config.max_monitoring_level,
        )

    def _facts_no_traffic(self):
        """Facts reflecting current controls but no new traffic (used to mask the action)."""
        return build_facts(
            [],
            self.controls,
            self.topology,
            finding_severity=self.finding_severity,
            step=self.step_idx,
            horizon=self.config.horizon,
            escalations_used=self.escalations_used,
            max_escalations=self.config.max_escalations,
            escalation_pending=self._timers.escalation > 0,
            max_monitoring_level=self.config.max_monitoring_level,
        )

    def _obs_mask(self, facts) -> tuple[np.ndarray, np.ndarray]:
        obs = from_platform_facts(facts, self.config.max_monitoring_level)
        mask = mask_from_facts(facts, self.config.max_monitoring_level)
        return obs, mask
