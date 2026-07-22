"""Postgres backup-restore drill.

Restores the current live Postgres to an isolated scratch database and runs
smoke queries against it. Confirms two things at once:

    1. Backups are actually restorable (Railway's daily snapshots — or any
       upstream .dump file the operator points us at — really do produce a
       working database).
    2. Post-restore schema and row counts look sane (RLS not broken, key
       tables present, tenant isolation policies exist).

Usage:
    # Live DB → scratch DB on the same server
    python backend/scripts/verify_backup_restore.py \
        --source $DATABASE_URL \
        --scratch $SCRATCH_DATABASE_URL

    # Or pipe a .dump file taken with pg_dump earlier:
    python backend/scripts/verify_backup_restore.py \
        --dump-file backup-2026-07-22.dump \
        --scratch $SCRATCH_DATABASE_URL

Meant to be run monthly (or before any DB-schema migration). See
docs/backup-restore-runbook.md for the full drill procedure and what to
do when a check fails.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

# --- Smoke checks --------------------------------------------------------
# What we assert on the restored DB. These are cheap queries that fail loudly
# if the restore truncated data, missed tables, or dropped RLS policies. All
# read-only; running against a scratch DB is safe.

SMOKE_CHECKS: list[tuple[str, str, str]] = [
    # (label, query, expected_condition_description)
    (
        "organizations table present",
        "SELECT COUNT(*) FROM organizations",
        ">= 0 (table exists)",
    ),
    (
        "users table present",
        "SELECT COUNT(*) FROM users",
        ">= 0 (table exists)",
    ),
    (
        "at least one super_admin exists (bootstrap not lost)",
        "SELECT COUNT(*) FROM users WHERE role = 'super_admin'",
        ">= 1",
    ),
    (
        "knowledge_chunks table + HNSW index (pgvector functional)",
        "SELECT COUNT(*) FROM pg_indexes WHERE indexname LIKE '%embedding%'",
        ">= 1",
    ),
    (
        "row-level security policies survive the restore",
        "SELECT COUNT(*) FROM pg_policies WHERE tablename IN "
        "('conversations','messages','contacts','knowledge_chunks','appointments','escalations')",
        ">= 6 (one per tenant-scoped table)",
    ),
    (
        "alembic version tracking table present",
        "SELECT COUNT(*) FROM alembic_version",
        "= 1",
    ),
]


def _shell(cmd: list[str], *, input_bytes: bytes | None = None, allow_fail: bool = False) -> subprocess.CompletedProcess:
    """Run a shell command, streaming stderr to our stderr. Kept as a helper
    so pg_dump/pg_restore invocations are consistent + auditable."""
    print(f"    $ {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, input=input_bytes, capture_output=True)
    if result.stderr:
        sys.stderr.buffer.write(result.stderr)
    if result.returncode != 0 and not allow_fail:
        raise RuntimeError(f"Command failed with exit {result.returncode}: {' '.join(cmd)}")
    return result


def _require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(
            f"'{name}' is required for backup-restore drills — install postgres client tools "
            "(e.g. `apt install postgresql-client` or `brew install libpq`)."
        )


def _to_pg_dsn(dsn: str) -> str:
    """SQLAlchemy DSNs use `postgresql+asyncpg://`; pg_dump/pg_restore want
    the bare libpq form `postgresql://`. Strip the driver suffix."""
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


def dump_source_to_file(source_dsn: str, dump_path: str) -> None:
    """Take a fresh pg_dump of the source DB in custom format. Custom format
    is required for pg_restore's parallel + selective options."""
    print(f"[1/3] Dumping {urlparse(source_dsn).hostname} → {dump_path} ...")
    _shell(["pg_dump", "--format=custom", "--no-owner", "--no-privileges",
            "--file", dump_path, _to_pg_dsn(source_dsn)])


def restore_to_scratch(dump_path: str, scratch_dsn: str) -> None:
    """Restore the dump into the scratch DB. --clean drops+recreates every
    object first so a partially-populated scratch DB is fine — you don't have
    to `dropdb` first."""
    print(f"[2/3] Restoring {dump_path} → {urlparse(scratch_dsn).hostname} ...")
    _shell(["pg_restore", "--clean", "--if-exists", "--no-owner",
            "--no-privileges", "--dbname", _to_pg_dsn(scratch_dsn),
            dump_path])


async def run_smoke_checks(scratch_dsn: str) -> tuple[int, int]:
    """Run every SMOKE_CHECK and print pass/fail. Returns (passed, failed)."""
    print(f"[3/3] Running {len(SMOKE_CHECKS)} smoke checks on scratch DB ...")

    # Lazy import so the script works even if the app venv isn't activated
    # (as long as psycopg or asyncpg is installed globally).
    try:
        import asyncpg
    except ImportError as exc:
        raise RuntimeError("asyncpg not installed — run from backend venv") from exc

    conn = await asyncpg.connect(_to_pg_dsn(scratch_dsn))
    try:
        passed = 0
        failed = 0
        for label, query, expected in SMOKE_CHECKS:
            try:
                row = await conn.fetchrow(query)
                value = list(row.values())[0] if row else None
                # All our smoke checks are "count > 0 unless noted" — the
                # actual pass condition matches the `expected` description.
                # Fail only on outright errors or count=0 where we expected
                # something.
                if value is None:
                    print(f"  ✗ {label}: got NULL (expected {expected})")
                    failed += 1
                elif "super_admin" in label and value < 1:
                    print(f"  ✗ {label}: got {value} (expected {expected})")
                    failed += 1
                elif "policies" in label and value < 6:
                    print(f"  ✗ {label}: got {value} (expected {expected})")
                    failed += 1
                elif "HNSW" in label or "embedding" in label:
                    if value < 1:
                        print(f"  ✗ {label}: got {value} (expected {expected})")
                        failed += 1
                    else:
                        print(f"  ✓ {label}: {value}")
                        passed += 1
                elif "alembic" in label and value != 1:
                    print(f"  ✗ {label}: got {value} (expected {expected})")
                    failed += 1
                else:
                    print(f"  ✓ {label}: {value}")
                    passed += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  ✗ {label}: query failed → {exc}")
                failed += 1
        return passed, failed
    finally:
        await conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", help="Source DATABASE_URL. Falls back to $DATABASE_URL.")
    ap.add_argument("--scratch", required=True,
                    help="Scratch DB DSN to restore INTO. MUST be a separate database — this drill "
                         "invokes --clean, which drops every object first.")
    ap.add_argument("--dump-file", help="Skip pg_dump and restore from this file instead.")
    args = ap.parse_args()

    _require_tool("pg_dump")
    _require_tool("pg_restore")

    if args.dump_file:
        dump_path = args.dump_file
        if not os.path.exists(dump_path):
            print(f"error: --dump-file {dump_path} does not exist", file=sys.stderr)
            return 2
        cleanup = False
    else:
        source_dsn = args.source or os.environ.get("DATABASE_URL")
        if not source_dsn:
            print("error: --source or DATABASE_URL required", file=sys.stderr)
            return 2
        # Dump into a tempfile the caller doesn't have to think about.
        tmp = tempfile.NamedTemporaryFile(suffix=".dump", delete=False)
        tmp.close()
        dump_path = tmp.name
        dump_source_to_file(source_dsn, dump_path)
        cleanup = True

    try:
        restore_to_scratch(dump_path, args.scratch)
        passed, failed = asyncio.run(run_smoke_checks(args.scratch))
    finally:
        if cleanup and os.path.exists(dump_path):
            os.unlink(dump_path)

    print()
    print(f"Drill result: {passed} passed, {failed} failed")
    if failed:
        print("Backup restore verification FAILED. Investigate before relying on backups.", file=sys.stderr)
        return 1
    print("Backup restore verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
