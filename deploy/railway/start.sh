#!/bin/sh
# Railway runs the API and the worker in one service so they share one volume
# (the artifact store and repository checkouts are local paths). Migrate first,
# then run both; if either exits, exit too so Railway restarts the container.
set -eu

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
