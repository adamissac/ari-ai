"""Post-run, pre-registered secondary: v8 on the train_v8 scenarios (train seeds, 14
episodes each, platform severity context), next to the pre-run table. Never holdout."""

import json
from pathlib import Path

from rl_defense.checkpoint import load_checkpoint
from rl_defense.live import evaluate as ev
from rl_defense.live.adversary import live_app
from rl_defense.live.scenarios import load_scenarios

HERE = Path(__file__).resolve().parent
agent, m = load_checkpoint(HERE / "candidate_online.pt")
lo = {**ev.V4_LOOP_OVERRIDES, "finding_severity_context": "platform"}
rows = ev.run_policy(
    ev.dqn_policy(agent),
    load_scenarios("train", subdir="train_v8"),
    live_app,
    episodes=14,
    action_space="live_v3",
    loop_overrides=lo,
)
out = {
    "_generated_by": "python results/live-retrain-v8/post_run_train_check.py",
    "checkpoint_sha256": m["checkpoint_sha256"],
    "train_v8": {
        s: {k: round(v[k], 3) for k in ("reward", "compromise_rate", "availability")}
        for s, v in ev.summarize_by_scenario(rows).items()
    },
}
(HERE / "post_run_train_check.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out["train_v8"], indent=1))
