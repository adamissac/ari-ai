#!/bin/sh
# Railway runs the API and the worker in one service so they share one volume
# (the artifact store and repository checkouts are local paths). Migrate first,
# then run both; if either exits, exit too so Railway restarts the container.
set -eu

# Every pusher and author by default; set a comma-separated list of logins to narrow it.
export GITHUB_AUTO_COMMIT_AUTHORS="${GITHUB_AUTO_COMMIT_AUTHORS-*}"

# Product model policy: Haiku 5.5 only, including every agent and fast path.
export ANTHROPIC_MODEL=claude-haiku-5-5
export ANTHROPIC_MODEL_FAST=claude-haiku-5-5
export AGENT_MODEL_OVERRIDES=""
export LLM_SERVER_FALLBACKS=false

hackatl-migrate

hackatl-worker &
worker=$!
hackatl-api &
api=$!

trap 'kill "$worker" "$api" 2>/dev/null || true' TERM INT

while kill -0 "$worker" 2>/dev/null && kill -0 "$api" 2>/dev/null; do
  sleep 2
done

echo "a process exited; stopping the service so Railway restarts it" >&2
kill "$worker" "$api" 2>/dev/null || true
wait || true
exit 1
