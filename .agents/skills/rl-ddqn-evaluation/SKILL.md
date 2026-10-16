---
name: rl-ddqn-evaluation
description: Train and evaluate a real Gymnasium/PyTorch Double DQN policy with reproducibility and honest simulated security metrics. Use for Adam RL work.
---

# rl-ddqn-evaluation


1. Implement `Env.reset/step`, hidden attacker state separate from noisy observations, valid action mask, seeded deterministic replay, horizon semantics and reward components.
2. Actual Double DQN has online and target networks, replay buffer, epsilon exploration, valid-mask online argmax for next action, target network evaluation, optimizer updates and periodic target sync. Test target math and gradient updates.
3. Implement baselines noop/random-valid/threshold rules, same held-out seeds/scenarios/reward config, training/evaluation separation and checkpoint metadata.
4. Run `gymnasium.utils.env_checker.check_env`; test seed determinism, no hidden-state leakage, isolation costs and realistic attacker retries.
5. Save raw trajectories, evaluation JSON, environment hash/seed/commit, confidence intervals and a failure case; never cherry-pick best seed or claim simulator accuracy transfers to real networks.
6. Inference produces typed `simulation_derived=true` recommendation; cannot execute real containment without separately designed validation and approval.
