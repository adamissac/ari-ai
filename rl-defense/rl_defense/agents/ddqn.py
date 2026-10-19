"""Double DQN (van Hasselt et al.) with action masking, replay buffer and target network.

Double DQN target for transition (s, a, r, s', done, mask'):

    a* = argmax_{a' valid in mask'} Q_online(s', a')
    y  = r + gamma * (1 - done) * Q_target(s', a*)

Online network selects, target network evaluates. Vanilla DQN would instead use
max_a' Q_target(s', a'); ``double_dqn_targets`` deliberately does not. Optional flags
(defaults reproduce protocol-v0): ``double=False`` for the vanilla-DQN ablation,
``dueling=True`` for a dueling head, ``n_step>1`` for n-step returns, in which case each
stored transition carries its own discount gamma**k (k = steps actually accumulated).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from pydantic import BaseModel, ConfigDict, Field
from torch import nn

NOOP = 0  # DefenseSimEnv's noop index (shared by every live action-space extension)

NEG_INF = -1e9


class DDQNConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hidden_sizes: tuple[int, ...] = (128, 128)
    gamma: float = Field(0.99, gt=0.0, le=1.0)
    lr: float = Field(1e-3, gt=0.0)
    lr_end: float | None = Field(
        None, gt=0.0, description="Linear decay lr -> lr_end over training"
    )
    batch_size: int = Field(64, ge=1)
    buffer_size: int = Field(100_000, ge=1)
    learning_starts: int = Field(1_000, ge=0)
    train_freq: int = Field(1, ge=1)
    target_update: str = Field("hard", pattern="^(hard|soft)$")
    target_update_interval: int = Field(1_000, ge=1)
    tau: float = Field(0.005, gt=0.0, le=1.0)
    eps_start: float = Field(1.0, ge=0.0, le=1.0)
    eps_end: float = Field(0.05, ge=0.0, le=1.0)
    eps_decay_steps: int = Field(50_000, ge=1)
    grad_clip: float = Field(10.0, gt=0.0)
    double: bool = True
    dueling: bool = False
    n_step: int = Field(1, ge=1, le=20)
    disruption_margin: float = Field(
        0.0,
        ge=0.0,
        description="Greedy abstention: take a disruptive action (rate_limit/isolate) only if its "
        "Q exceeds the best valid non-disruptive action's Q by at least this margin. 0 = off.",
    )
    noop_margin: float = Field(
        0.0,
        ge=0.0,
        description="Greedy abstention: take any non-noop action only if its Q exceeds Q(noop) "
        "by at least this margin (live v3: effect-free actions win argmax ties by noise). 0 = off.",
    )
    eps_disruptive_weight: float | None = Field(
        None,
        gt=0.0,
        le=1.0,
        description="Exploration: relative probability weight of disruptive actions when "
        "acting randomly (None = uniform over valid actions, the v0/v1 behaviour).",
    )


class QNetwork(nn.Module):
    def __init__(self, obs_dim: int, n_actions: int, hidden: tuple[int, ...]) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        prev = obs_dim
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.ReLU()]
            prev = h
        layers.append(nn.Linear(prev, n_actions))
        self.net = nn.Sequential(*layers)

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.net(obs)


class DuelingQNetwork(nn.Module):
    """Q(s,a) = V(s) + A(s,a) - mean_a A(s,a) (Wang et al.)."""

    def __init__(self, obs_dim: int, n_actions: int, hidden: tuple[int, ...]) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        prev = obs_dim
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.ReLU()]
            prev = h
        self.trunk = nn.Sequential(*layers)
        self.value = nn.Linear(prev, 1)
        self.advantage = nn.Linear(prev, n_actions)

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        z = self.trunk(obs)
        adv = self.advantage(z)
        return self.value(z) + adv - adv.mean(dim=-1, keepdim=True)


def build_q_network(obs_dim: int, n_actions: int, config: DDQNConfig) -> nn.Module:
    cls = DuelingQNetwork if config.dueling else QNetwork
    return cls(obs_dim, n_actions, config.hidden_sizes)


@dataclass
class Batch:
    obs: torch.Tensor
    actions: torch.Tensor
    rewards: torch.Tensor
    next_obs: torch.Tensor
    dones: torch.Tensor
    next_masks: torch.Tensor
    discounts: torch.Tensor | None = None  # per-transition gamma**k for n-step; None = gamma


class ReplayBuffer:
    """Uniform replay storing (obs, action, reward, next_obs, done, next_action_mask, discount)."""

    def __init__(self, capacity: int, obs_dim: int, n_actions: int, seed: int) -> None:
        self.capacity = capacity
        self.obs = np.zeros((capacity, obs_dim), dtype=np.float32)
        self.next_obs = np.zeros((capacity, obs_dim), dtype=np.float32)
        self.actions = np.zeros(capacity, dtype=np.int64)
        self.rewards = np.zeros(capacity, dtype=np.float32)
        self.dones = np.zeros(capacity, dtype=np.float32)
        self.next_masks = np.zeros((capacity, n_actions), dtype=bool)
        self.discounts = np.full(capacity, np.nan, dtype=np.float32)
        self._pos = 0
        self._full = False
        self._rng = np.random.default_rng(seed)

    def __len__(self) -> int:
        return self.capacity if self._full else self._pos

    def add(self, obs, action, reward, next_obs, done, next_mask, discount=None) -> None:  # noqa: ANN001
        i = self._pos
        self.obs[i], self.actions[i], self.rewards[i] = obs, action, reward
        self.next_obs[i], self.dones[i], self.next_masks[i] = next_obs, float(done), next_mask
        self.discounts[i] = np.nan if discount is None else discount
        self._pos = (self._pos + 1) % self.capacity
        self._full = self._full or self._pos == 0

    def sample(self, batch_size: int) -> Batch:
        idx = self._rng.integers(0, len(self), size=batch_size)
        return Batch(
            obs=torch.as_tensor(self.obs[idx]),
            actions=torch.as_tensor(self.actions[idx]),
            rewards=torch.as_tensor(self.rewards[idx]),
            next_obs=torch.as_tensor(self.next_obs[idx]),
            dones=torch.as_tensor(self.dones[idx]),
            next_masks=torch.as_tensor(self.next_masks[idx]),
            discounts=None
            if np.isnan(self.discounts[idx]).all()
            else torch.as_tensor(self.discounts[idx]),
        )


class NStepAccumulator:
    """Turns 1-step transitions into n-step ones: R = sum_k gamma^k r_k, discount = gamma^n.

    On termination the remaining partial windows are flushed with done=1; on truncation
    (time limit) they are flushed with done=0 and discount gamma^k for k accumulated steps.
    """

    def __init__(self, n: int, gamma: float) -> None:
        self.n, self.gamma = n, gamma
        self._window: list[tuple] = []

    def push(self, obs, action, reward, next_obs, terminated, truncated, next_mask) -> list[tuple]:  # noqa: ANN001
        self._window.append((obs, action, reward))
        out: list[tuple] = []
        if len(self._window) == self.n and not (terminated or truncated):
            out.append(self._emit(next_obs, False, next_mask))
            self._window.pop(0)
        if terminated or truncated:
            while self._window:
                out.append(self._emit(next_obs, terminated, next_mask))
                self._window.pop(0)
        return out

    def _emit(self, next_obs, done, next_mask) -> tuple:  # noqa: ANN001
        ret = sum(self.gamma**k * r for k, (_, _, r) in enumerate(self._window))
        obs, action, _ = self._window[0]
        return (obs, action, ret, next_obs, done, next_mask, self.gamma ** len(self._window))


def masked_argmax(q: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    return torch.where(mask, q, torch.full_like(q, NEG_INF)).argmax(dim=-1)


def double_dqn_targets(
    online: nn.Module, target: nn.Module, batch: Batch, gamma: float
) -> torch.Tensor:
    """y = r + gamma * (1 - done) * Q_target(s', argmax_valid Q_online(s'))."""
    with torch.no_grad():
        next_actions = masked_argmax(online(batch.next_obs), batch.next_masks)
        next_q = target(batch.next_obs).gather(1, next_actions.unsqueeze(1)).squeeze(1)
        disc = gamma if batch.discounts is None else batch.discounts
        return batch.rewards + disc * (1.0 - batch.dones) * next_q


def dqn_targets(target: nn.Module, batch: Batch, gamma: float) -> torch.Tensor:
    """Vanilla DQN (ablation only): y = r + gamma * (1 - done) * max_valid Q_target(s')."""
    with torch.no_grad():
        q_next = target(batch.next_obs)
        next_q = (
            torch.where(batch.next_masks, q_next, torch.full_like(q_next, NEG_INF)).max(-1).values
        )
        disc = gamma if batch.discounts is None else batch.discounts
        return batch.rewards + disc * (1.0 - batch.dones) * next_q


def disruptive_action_mask(n_actions: int) -> np.ndarray:
    """Boolean mask of disruptive actions (rate_limit / isolate) for DefenseSimEnv's layout."""
    from rl_defense.envs.defense_sim import DISRUPTIVE, N_ACTIONS, decode_action

    if n_actions != N_ACTIONS:
        return np.zeros(n_actions, dtype=bool)
    return np.array([decode_action(a)[0] in DISRUPTIVE for a in range(n_actions)])


class DDQNAgent:
    def __init__(self, obs_dim: int, n_actions: int, config: DDQNConfig, seed: int) -> None:
        self.obs_dim, self.n_actions, self.config = obs_dim, n_actions, config
        self.disruptive = disruptive_action_mask(n_actions)
        torch.manual_seed(seed)
        self.online = build_q_network(obs_dim, n_actions, config)
        self.target = build_q_network(obs_dim, n_actions, config)
        self.target.load_state_dict(self.online.state_dict())
        self.target.requires_grad_(False)
        self.optimizer = torch.optim.Adam(self.online.parameters(), lr=config.lr)
        self._rng = np.random.default_rng(seed)
        self.updates = 0

    def epsilon(self, step: int) -> float:
        c = self.config
        frac = min(1.0, step / c.eps_decay_steps)
        return c.eps_start + frac * (c.eps_end - c.eps_start)

    def q_values(self, obs: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            return self.online(torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0))[0].numpy()

    def greedy_action(self, obs: np.ndarray, mask: np.ndarray) -> int:
        """Masked argmax, with the optional disruption margin (abstain unless clearly better)."""
        q = self.q_values(obs)
        qm = np.where(mask, q, NEG_INF)
        best = int(np.argmax(qm))
        margin = self.config.disruption_margin
        if margin > 0.0 and self.disruptive[best]:
            safe = mask & ~self.disruptive
            if safe.any():
                alt = int(np.argmax(np.where(safe, q, NEG_INF)))
                if q[best] - q[alt] < margin:
                    best = alt
        nm = self.config.noop_margin
        if nm > 0.0 and best != NOOP and mask[NOOP] and q[best] - q[NOOP] < nm:
            return NOOP
        return best

    def act(self, obs: np.ndarray, mask: np.ndarray, epsilon: float = 0.0) -> int:
        """Epsilon-greedy over VALID actions only."""
        valid = np.flatnonzero(mask)
        if self._rng.random() < epsilon:
            w = self.config.eps_disruptive_weight
            if w is None:
                return int(self._rng.choice(valid))
            weights = np.where(self.disruptive[valid], w, 1.0)
            return int(self._rng.choice(valid, p=weights / weights.sum()))
        return self.greedy_action(obs, mask)

    def update(self, batch: Batch) -> dict[str, float]:
        c = self.config
        if c.double:
            y = double_dqn_targets(self.online, self.target, batch, c.gamma)
        else:
            y = dqn_targets(self.target, batch, c.gamma)
        q = self.online(batch.obs).gather(1, batch.actions.unsqueeze(1)).squeeze(1)
        loss = nn.functional.smooth_l1_loss(q, y)
        self.optimizer.zero_grad()
        loss.backward()
        grad_norm = nn.utils.clip_grad_norm_(self.online.parameters(), c.grad_clip)
        self.optimizer.step()
        self.updates += 1
        if c.target_update == "soft":
            self.soft_update(c.tau)
        elif self.updates % c.target_update_interval == 0:
            self.hard_update()
        return {
            "loss": loss.item(),
            "grad_norm": float(grad_norm),
            "q_mean": q.detach().mean().item(),
        }

    def hard_update(self) -> None:
        self.target.load_state_dict(self.online.state_dict())

    def soft_update(self, tau: float) -> None:
        with torch.no_grad():
            for t, o in zip(self.target.parameters(), self.online.parameters(), strict=True):
                t.mul_(1.0 - tau).add_(o, alpha=tau)

    def state_dict(self) -> dict:
        return {
            "online": self.online.state_dict(),
            "target": self.target.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "updates": self.updates,
        }

    def load_state_dict(self, state: dict) -> None:
        self.online.load_state_dict(state["online"])
        self.target.load_state_dict(state["target"])
        self.optimizer.load_state_dict(state["optimizer"])
        self.updates = state["updates"]
