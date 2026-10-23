#!/bin/sh
# Railway runs the API and the worker in one service so they share one volume
# (the artifact store and repository checkouts are local paths). Migrate first,
# then run both; if either exits, exit too so Railway restarts the container.
set -eu

# Every pusher and author by default; set a comma-separated list of logins to narrow it.
export GITHUB_AUTO_COMMIT_AUTHORS="${GITHUB_AUTO_COMMIT_AUTHORS-*}"

# RL defense policy retrained from results/protocol-v1/candidate.yaml (seed 0); the worker
# refuses a checkpoint whose sha256 differs from this pin.
RL_DIR=/app/rl-defense
export RL_CHECKPOINT_PATH="${RL_CHECKPOINT_PATH-$RL_DIR/results/protocol-v1-retrain/checkpoints/ddqn_seed0.pt}"
export RL_CHECKPOINT_SHA256="${RL_CHECKPOINT_SHA256-666145e00d4ee3b9a1839179d9d9aca5a245c20fe7a173e2cb960e34e0393fe8}"
export RL_TOPOLOGY_PATH="${RL_TOPOLOGY_PATH-$RL_DIR/configs/topology/payments_lite.yaml}"

# Product model policy: Haiku 5.5 only, including every agent and fast path.
export ANTHROPIC_MODEL=claude-haiku-5-5
export ANTHROPIC_MODEL_FAST=claude-haiku-5-5
export AGENT_MODEL_OVERRIDES=""
export LLM_SERVER_FALLBACKS=false

hackatl-migrate

# Several workers so one long assessment does not hold up every other commit; jobs are
# claimed with SKIP LOCKED, so they never run the same job twice.
pids=""
i=0
while [ "$i" -lt "${WORKER_PROCESSES:-3}" ]; do
  hackatl-worker &
  pids="$pids $!"
  i=$((i + 1))
done
hackatl-api &
pids="$pids $!"

trap 'kill $pids 2>/dev/null || true' TERM INT

alive() {
  for p in $pids; do kill -0 "$p" 2>/dev/null || return 1; done
}
while alive; do
  sleep 2
done

echo "a process exited; stopping the service so Railway restarts it" >&2
kill $pids 2>/dev/null || true
wait || true
exit 1
