#!/bin/sh
set -eu

export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-3000}"

node /app/scripts/materialize-env.mjs

echo "[iguana] Starting Astro server on ${HOST}:${PORT}"
exec node /app/dist/server/entry.mjs
