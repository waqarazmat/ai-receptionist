#!/usr/bin/env bash
# DEPRECATED / no-op. Migrations used to run here as Railway's preDeployCommand,
# but the one-shot pre-deploy container could not reach Postgres over the
# private network (it fell back to the public proxy and the SSL handshake got
# reset — "[Errno 104] Connection reset by peer"), which aborted every deploy.
#
# Migrations now run in railway-start.sh, inside the MAIN app container (which
# reaches Postgres reliably), for the web service only. railway.toml no longer
# references this file. Kept as a no-op so any stale reference can't run alembic
# in the unreachable pre-deploy container again.
echo "railway-predeploy: no-op (migrations moved to railway-start.sh)"
exit 0
