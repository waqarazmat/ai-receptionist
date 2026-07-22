# Postgres backup-restore drill runbook

Railway takes automatic daily snapshots of the Postgres service. Untested
backups are a fiction — this doc is the procedure that turns them into a
real recovery capability.

**Run the drill monthly**, and once before every schema-changing migration.

## What "verified" means here

The drill has two goals:

1. **Restorability.** A snapshot really can be loaded back into an empty DB
   without pg_restore errors.
2. **Schema + tenant-isolation integrity.** The restored DB has every table
   the app expects, at least one super-admin row (bootstrap not lost), the
   HNSW index on `knowledge_chunks.embedding`, and RLS policies on every
   tenant-scoped table.

If step 2 fails, the backup exists but is not usable — usually because
pgvector or an extension wasn't included in the dump.

## Prerequisites

- `pg_dump` and `pg_restore` on the machine running the drill. Match the
  major version to the source server: v16 client can restore v16 dumps but
  not v17. Check with `psql --version` on the server first.
- A **scratch Postgres database** — must be a separate DB, not the live
  one. The script runs `pg_restore --clean` which drops every object first.
  Options:
    - A second Railway Postgres service in a non-prod project ("prod-drills")
    - A local Postgres container: `docker run -p 5433:5432 -e POSTGRES_PASSWORD=x pgvector/pgvector:pg16`
    - A Railway one-shot job with an ephemeral DB
- `asyncpg` in the environment running the script (already in
  `backend/requirements.txt`).

## Running the drill

### Option A: dump-then-restore (most common)

```bash
cd backend

# Live DB → scratch DB in one step (dumps to a tempfile that's cleaned up)
python scripts/verify_backup_restore.py \
  --source "$DATABASE_URL" \
  --scratch "postgresql://postgres:x@localhost:5433/postgres"
```

Expected output ends with:

```
Drill result: 6 passed, 0 failed
Backup restore verification passed.
```

### Option B: restore from a specific dump file

Use this after downloading a snapshot from Railway's dashboard or after
running `pg_dump` manually earlier:

```bash
python scripts/verify_backup_restore.py \
  --dump-file backup-2026-07-22.dump \
  --scratch "postgresql://postgres:x@localhost:5433/postgres"
```

## What the smoke checks assert (and what a failure means)

| Check | Failure means |
|---|---|
| `organizations` / `users` tables present | Dump is missing schema — most likely `pg_dump` was run without the app database name or against the wrong host |
| At least one super_admin row | Bootstrap user missing. Restoring this DB would lock everyone out. Check whether the source DB is empty or `pg_dump --schema-only` was used by mistake |
| HNSW index on `knowledge_chunks.embedding` | pgvector extension not included in the dump. Fix by installing pgvector on the scratch DB *before* restoring: `CREATE EXTENSION vector;` |
| RLS policies on 6+ tenant-scoped tables | RLS policies were dropped. Multi-tenant isolation is broken on this restore. Check pg_dump command — should NOT use `--exclude-table` or `--schema-only` |
| `alembic_version` table with exactly 1 row | Migrations tracking is off. Restored DB will re-run migrations from scratch, which is destructive if the schema doesn't match |

## When a drill fails

1. **Do NOT delete the failing dump.** It's evidence.
2. Rerun the drill against a *different* recent backup — if that one passes,
   the specific snapshot was the problem.
3. Check Railway's snapshot logs for errors around the failing snapshot's
   timestamp.
4. If two consecutive snapshots fail: **stop relying on automatic backups
   immediately**. Take a manual `pg_dump` right now and archive it off-site
   until snapshots are fixed.
5. File an issue with the failure output pasted in.

## Costs

Each drill:
- ~30-60 s of pg_dump time on production (read-only, low impact)
- Local disk for the tempfile (usually <100 MB for a fresh install; grows
  linearly with `knowledge_chunks` size)
- Scratch DB storage (freed after each run if you `DROP DATABASE`)

If run monthly, that's ~12 minutes of prod DB CPU per year in exchange
for known-good backups.

## Related

- `backend/scripts/verify_backup_restore.py` — the drill script itself
- Root `CLAUDE.md` — security rule #8 (graceful degradation) is where
  restore-time behaviour should be documented if it ever changes
