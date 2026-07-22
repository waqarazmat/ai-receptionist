"""Super-admin CSV exports.

Streaming responses so an audit-log export doesn't buffer the whole table
in memory — Postgres cursor + row-by-row yield keeps memory flat regardless
of table size.

SOC 2 / compliance folks generally want: who did what, when, from where,
and what they changed. That's exactly what audit_logs stores. Format the
columns for Excel-friendly reading (ISO timestamps, JSON details in a
single trailing column).
"""

import csv
import io
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_db_session
from app.models.audit_log import AuditLog

router = APIRouter()


def _iso_date_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


async def _stream_csv(header: list[str], rows_iter, filename: str) -> StreamingResponse:
    """Wrap an async row iterator into a StreamingResponse producing a
    CSV file. `rows_iter` yields lists that match `header` in width."""

    async def generator():
        # `csv` writes to a text buffer we flush after every row. Using a
        # fresh StringIO per row keeps it simple; the memory it holds is
        # exactly one row of data.
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(header)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        async for row in rows_iter:
            writer.writerow(row)
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    return StreamingResponse(
        generator(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/audit-logs/export.csv")
async def export_audit_logs(
    db: AsyncSession = Depends(get_admin_db_session),
) -> StreamingResponse:
    """Full audit-log dump as CSV. Chronological (oldest first) so the
    exported file reads as an event timeline.

    Deliberately no filters (date range / user / action) on this endpoint —
    the audit-log UI page already has filtered views; this endpoint is the
    "give me everything for our auditor" workflow.
    """
    header = [
        "id", "created_at_utc", "user_id", "action",
        "target_type", "target_id", "ip_address", "details_json",
    ]

    async def rows():
        result = await db.stream(
            select(AuditLog).order_by(AuditLog.created_at.asc())
        )
        async for chunk in result.scalars().partitions(200):
            for entry in chunk:
                yield [
                    str(entry.id),
                    entry.created_at.isoformat() if entry.created_at else "",
                    str(entry.user_id) if entry.user_id else "",
                    entry.action,
                    entry.target_type or "",
                    str(entry.target_id) if entry.target_id else "",
                    entry.ip_address or "",
                    json.dumps(entry.details or {}, default=str),
                ]

    return await _stream_csv(header, rows(), f"audit-logs-{_iso_date_slug()}.csv")
