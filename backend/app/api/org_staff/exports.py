"""Org-staff CSV exports. Org-scoped: current user can only export their
own tenant's data (RLS enforces this at the DB layer even if we forgot to
filter — defence in depth per root CLAUDE.md rule)."""

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_org_staff
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.user import User

router = APIRouter()


def _slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


async def _csv_response(header: list[str], rows_iter, filename: str) -> StreamingResponse:
    async def generator():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(header)
        yield buffer.getvalue()
        buffer.seek(0); buffer.truncate(0)
        async for row in rows_iter:
            writer.writerow(row)
            yield buffer.getvalue()
            buffer.seek(0); buffer.truncate(0)

    return StreamingResponse(
        generator(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/conversations/export.csv")
async def export_conversations(
    current_user: User = Depends(require_org_staff),
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """One row per conversation. Joins Contact for the display name so the
    CSV is readable without another lookup."""
    header = [
        "id", "channel", "status", "contact_name", "contact_id",
        "assigned_to", "last_message_at_utc", "created_at_utc",
    ]

    async def rows():
        stmt = (
            select(Conversation, Contact.name)
            .join(Contact, Contact.id == Conversation.contact_id, isouter=True)
            .where(Conversation.org_id == current_user.org_id)
            .order_by(Conversation.created_at.desc())
        )
        result = await db.stream(stmt)
        async for chunk in result.partitions(200):
            for conv, contact_name in chunk:
                yield [
                    str(conv.id),
                    conv.channel.value,
                    conv.status.value,
                    contact_name or "",
                    str(conv.contact_id) if conv.contact_id else "",
                    str(conv.assigned_to) if conv.assigned_to else "",
                    conv.last_message_at.isoformat() if conv.last_message_at else "",
                    conv.created_at.isoformat() if conv.created_at else "",
                ]

    return await _csv_response(header, rows(), f"conversations-{_slug()}.csv")


@router.get("/appointments/export.csv")
async def export_appointments(
    current_user: User = Depends(require_org_staff),
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """One row per appointment. Includes both start and end (org's timezone
    is not applied here — CSV consumers usually want UTC and can convert)."""
    header = [
        "id", "status", "service", "start_time_utc", "end_time_utc",
        "contact_id", "google_calendar_event_id", "created_at_utc",
    ]

    async def rows():
        stmt = (
            select(Appointment)
            .where(Appointment.org_id == current_user.org_id)
            .order_by(Appointment.start_time.desc())
        )
        result = await db.stream(stmt)
        async for chunk in result.scalars().partitions(200):
            for appt in chunk:
                yield [
                    str(appt.id),
                    appt.status.value,
                    appt.service or "",
                    appt.start_time.isoformat() if appt.start_time else "",
                    appt.end_time.isoformat() if appt.end_time else "",
                    str(appt.contact_id) if appt.contact_id else "",
                    appt.google_calendar_event_id or "",
                    appt.created_at.isoformat() if appt.created_at else "",
                ]

    return await _csv_response(header, rows(), f"appointments-{_slug()}.csv")
