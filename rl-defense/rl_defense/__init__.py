"""Simulated cyber-defense RL: DefenseSimEnv, Double DQN, baselines, evaluation.

Everything in this package runs in simulation. Policies produce recommendations
only; there is no code path from a recommendation to a real-world action.
"""

__version__ = "0.1.0"
ENV_ID = "DefenseSimEnv-v0"
SIMULATION_CAVEAT = "Recommendation from a policy trained in simulation. Not applied automatically."
