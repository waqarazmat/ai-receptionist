#!/usr/bin/env bash
# ONE start command for BOTH Railway services built from this same image.
# Selected at runtime (deploy time), NOT build time, by the RUN_WORKER env var:
#
#   worker service : set RUN_WORKER=true  -> runs the arq background worker
#   web service    : leave RUN_WORKER unset -> runs the FastAPI web server
#
# This avoids per-service start-command overrides in the dashboard (which kept
# getting mis-set as a *build* command, running arq during the image build).
set -e

if [ "${RUN_WORKER}" = "true" ]; then
  echo "railway-start: launching ARQ worker (RUN_WORKER=true)"
  exec arq app.tasks.worker.WorkerSettings
else
  # WEB_CONCURRENCY controls uvicorn worker processes (default 1 = unchanged).
  # NOTE: each worker loads the embedding model (~0.5-1GB RAM), and running >1
  # worker REQUIRES SOCKETIO_REDIS_MANAGER=true or cross-worker Socket.IO
  # delivery breaks. Keep workers * (DB_POOL_SIZE+DB_MAX_OVERFLOW) under Postgres
  # max_connections.
  echo "railway-start: launching web server (workers=${WEB_CONCURRENCY:-1})"
  exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WEB_CONCURRENCY:-1}"
fi
