#!/usr/bin/env bash
# preDeployCommand shared by BOTH Railway services (single railway.toml).
#
# Only the WEB service runs DB migrations. The WORKER (RUN_WORKER=true) skips
# them: it doesn't need to migrate, and running `alembic upgrade head` in the
# worker's one-shot pre-deploy container was failing to reach Postgres and
# aborting the whole deploy.
set -e

if [ "${RUN_WORKER}" = "true" ]; then
  echo "railway-predeploy: worker service — skipping migrations (the web service runs them)"
  exit 0
fi

# The one-shot pre-deploy container intermittently fails to reach Postgres — the
# connection gets reset mid-SSL-handshake ("[Errno 104] Connection reset by
# peer") — which aborts the ENTIRE deploy even when the migration itself is
# fine. Retry a few times with a short backoff so a transient network blip
# doesn't block a deploy; only give up (and abort) after they all fail.
attempts="${MIGRATION_RETRIES:-5}"
for i in $(seq 1 "$attempts"); do
  echo "railway-predeploy: alembic upgrade head (attempt $i/$attempts)"
  if alembic upgrade head; then
    echo "railway-predeploy: migrations applied on attempt $i"
    exit 0
  fi
  if [ "$i" -lt "$attempts" ]; then
    echo "railway-predeploy: attempt $i failed (likely a transient DB connection) — retrying in 5s"
    sleep 5
  fi
done

echo "railway-predeploy: migrations still failing after $attempts attempts — aborting deploy"
exit 1
