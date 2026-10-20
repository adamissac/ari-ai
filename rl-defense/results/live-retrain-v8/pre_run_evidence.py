"""Pre-registration evidence for v8: train_v8 new scenarios and val_v4, never holdout."""

import json
import sys
from pathlib import Path

from rl_defense.checkpoint import load_checkpoint
from rl_defense.envs import default_config_paths, load_configs
from rl_defense.live import evaluate as ev
from rl_defense.live.adversary import live_app
from rl_defense.live.scenarios import load_scenarios
from rl_defense.train import train

out = Path(sys.argv[1])
base = out / "base" / "ddqn_seed0.pt"
if not base.exists():
    train(
        load_configs(default_config_paths("train")),
        seed=0,
        steps=30000,
        run_dir=out / "base",
        log_every=30000,
    )
dep, dm = load_checkpoint(base)
v7, _ = load_checkpoint(Path("results/live-retrain-v7/candidate_online.pt"))
v6, _ = load_checkpoint(Path("results/live-retrain-v6/candidate_online.pt"))
rules = json.loads(Path("results/live-retrain-v7/rules_tuning.json").read_text())["selected"]
lo = {**ev.V4_LOOP_OVERRIDES, "finding_severity_context": "platform"}
pol = {
    "deployed": ev.dqn_policy(dep),
    "v7": ev.dqn_policy(v7),
    "v6": ev.dqn_policy(v6),
    "rules_v7": ev.rules_policy(rules),
    "noop": ev.noop_policy,
    "always_block_principal": ev.always_block_principal,
}
tr = [s for s in load_scenarios("train", subdir="train_v8")]
va = load_scenarios("val", subdir="val_v4")
res = {"deployed_sha": dm["checkpoint_sha256"]}
for split, scs, n in (("train_v8", tr, 14), ("val_v4", va, 8)):
    res[split] = {}
    for k, p in pol.items():
        rows = ev.run_policy(
            p, scs, live_app, episodes=n, action_space="live_v3", loop_overrides=lo
        )
        res[split][k] = {
            s: {m: round(v[m], 3) for m in ("reward", "compromise_rate", "availability")}
            for s, v in ev.summarize_by_scenario(rows).items()
        }
        print(split, k, {s: v["reward"] for s, v in res[split][k].items()}, flush=True)
(out / "pre_v8.json").write_text(json.dumps(res, indent=2))
