"""Simulated cyber-defense RL: DefenseSimEnv, Double DQN, baselines, evaluation.

Everything in this package runs in simulation. Policies produce recommendations
only; there is no code path from a recommendation to a real-world action.
"""

__version__ = "0.1.0"
ENV_ID = "DefenseSimEnv-v0"
# Must equal shared.rl.SIMULATION_CAVEAT_DEFAULT (asserted in tests/test_shared_contract.py).
SIMULATION_CAVEAT = (
    "Simulation-derived recommendation from a policy trained only in DefenseSimEnv; "
    "not a detection of a real attack and never executed automatically."
)
