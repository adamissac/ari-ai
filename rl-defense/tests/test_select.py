"""The validation harness must never touch held-out configs, eval seeds or final training seeds."""

import pytest

from experiments.select import (
    FORBIDDEN_EPISODE_SEEDS,
    FORBIDDEN_TRAIN_SEEDS,
    VAL_EPISODE_SEEDS,
    VAL_TRAIN_SEEDS,
    run_job,
    summarize,
)


def test_validation_seeds_are_disjoint_from_reserved_seeds():
    assert not set(VAL_EPISODE_SEEDS) & set(FORBIDDEN_EPISODE_SEEDS)
    assert not set(VAL_TRAIN_SEEDS) & set(FORBIDDEN_TRAIN_SEEDS)


def test_run_job_refuses_final_training_seeds(tmp_path):
    with pytest.raises(AssertionError, match="reserved"):
        run_job("x", 10, {}, 0, str(tmp_path))


def test_summarize_ranks_by_mean_return_and_reports_worst_seed():
    def job(name, seed, ret):
        pooled = dict.fromkeys(
            [
                "compromise_rate",
                "db_loss_rate",
                "false_disruption_rate",
                "service_uptime",
                "escalations",
                "impact_gateway",
                "impact_api",
                "impact_auth",
                "impact_payments",
                "impact_db",
            ],
            0.0,
        )
        pooled["return"] = ret
        return {"candidate": name, "seed": seed, "steps": 1, "overrides": {}, "pooled": pooled}

    rows = summarize([job("a", 10, -50), job("a", 11, -70), job("b", 10, -55), job("b", 11, -57)])
    assert [r["candidate"] for r in rows] == ["b", "a"]
    assert rows[1]["worst_seed_return"] == -70
