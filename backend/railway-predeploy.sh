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
else
  echo "railway-predeploy: running alembic upgrade head"
  exec alembic upgrade head
fi
