"""CLI: run the live defense loop against the owned demo app and record evidence.

    # train a short policy and run 3 live episodes, writing transitions + a summary
    python -m rl_defense.live.run --steps 20000 --episodes 3 --horizon 30 \
        --out runs/live/transitions.jsonl

    # or drive an existing checkpoint
    python -m rl_defense.live.run --checkpoint runs/protocol-v1/ddqn_seed0.pt --episodes 3

Everything the loop reports is measured from real HTTP outcomes against
``examples/payments-lite`` running in-process. Numbers are lab evidence only (RQ-005).
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import tempfile

from payments_lite.app import create_app

from rl_defense.envs import default_config_paths, load_configs
from rl_defense.inference import PolicyRunner
from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
from rl_defense.train import train


def _get_runner(args: argparse.Namespace) -> tuple[PolicyRunner, str]:
    if args.checkpoint:
        return PolicyRunner(pathlib.Path(args.checkpoint)), args.checkpoint
    cfgs = load_configs(default_config_paths("train"))
    d = pathlib.Path(tempfile.mkdtemp(prefix="live_ckpt_"))
    train(cfgs, seed=args.seed, steps=args.steps, run_dir=d, log_every=max(1, args.steps))
    path = d / f"ddqn_seed{args.seed}.pt"
    return PolicyRunner(path), str(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checkpoint", default=None, help="checkpoint .pt (else train a short one)")
    ap.add_argument("--steps", type=int, default=20000, help="train steps when no checkpoint given")
    ap.add_argument("--episodes", type=int, default=3)
    ap.add_argument("--horizon", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None, help="write transitions as JSONL to this path")
    args = ap.parse_args(argv)

    runner, ckpt = _get_runner(args)
    loop = LiveDefenseLoop(create_app, runner, config=LoopConfig(horizon=args.horizon))
    out_fh = None
    if args.out:
        p = pathlib.Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        out_fh = p.open("w")

    summaries = []
    try:
        for ep in range(args.episodes):
            ts = loop.run_episode(seed=1000 + ep)
            total_r = sum(t.reward for t in ts)
            compromised = sum(t.outcome.compromised_reads for t in ts)
            attacks = sum(t.outcome.attack_requests for t in ts)
            benign_blocked = sum(t.outcome.benign_blocked for t in ts)
            benign = sum(t.outcome.benign_requests for t in ts)
            actions = collections.Counter(t.outcome.action_label for t in ts)
            summaries.append(
                {
                    "episode": ep,
                    "steps": len(ts),
                    "total_reward": round(total_r, 3),
                    "compromised_reads": compromised,
                    "attack_requests": attacks,
                    "benign_blocked": benign_blocked,
                    "benign_requests": benign,
                    "actions": dict(actions),
                }
            )
            if out_fh:
                for t in ts:
                    out_fh.write(json.dumps({"episode": ep, **t.model_dump()}) + "\n")
    finally:
        loop.close()
        if out_fh:
            out_fh.close()

    print(f"policy checkpoint: {ckpt}")
    print(f"policy_version:    {runner.policy_version}")
    print("-" * 78)
    hdr = f"{'ep':>2} {'reward':>9} {'compromised':>12} {'attacks':>8} {'benign_blk':>11} {'benign':>7}"
    print(hdr)
    for s in summaries:
        print(
            f"{s['episode']:>2} {s['total_reward']:>9} {s['compromised_reads']:>12} "
            f"{s['attack_requests']:>8} {s['benign_blocked']:>11} {s['benign_requests']:>7}"
        )
    print("-" * 78)
    for s in summaries:
        print(f"ep{s['episode']} actions: {s['actions']}")
    print(
        "\nNOTE: measured from real HTTP outcomes against examples/payments-lite in-process. "
        "The policy here is trained on the abstract simulator; its behavior on real telemetry "
        "is itself a research question (RQ-005). Numbers are lab evidence, not real-world proof."
    )
    if args.out:
        print(f"\ntransitions written to {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
