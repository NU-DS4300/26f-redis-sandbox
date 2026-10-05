#!/bin/sh
# Loads seed.redis into Redis. Skips if the database already has keys, unless FORCE=1
# (which FLUSHALLs first). Runs inside the redis image via the `seed` compose service.
set -eu

HOST="${REDIS_HOST:-redis}"
PORT="${REDIS_PORT:-6379}"
SEED_FILE="${SEED_FILE:-/seed/seed.redis}"
cli() { redis-cli -h "$HOST" -p "$PORT" "$@"; }

keys="$(cli DBSIZE)"
if [ "$keys" -gt 0 ]; then
  if [ "${FORCE:-0}" != "1" ]; then
    echo "Redis already has $keys keys; skipping seed (set FORCE=1 to wipe and reload)."
    exit 0
  fi
  echo "FORCE=1: flushing $keys keys."
  cli FLUSHALL >/dev/null
fi

# Strip comments/blank lines. --pipe sends everything in one go, prints each error reply,
# and exits non-zero if any command failed.
if ! grep -v -e '^#' -e '^[[:space:]]*$' "$SEED_FILE" | cli --pipe; then
  echo "Seed failed (see errors above)." >&2
  exit 1
fi
echo "Seed complete: $(cli DBSIZE) keys loaded."
