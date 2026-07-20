import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.enums import AppointmentStatus, ConversationStatus, EscalationStatus
from app.models.escalation import Escalation
from app.models.message import Message
from app.models.organization import Organization


async def get_dashboard_stats(db: AsyncSession) -> dict:
    total_orgs = (await db.execute(select(func.count(Organization.id)))).scalar_one()
    active_orgs = (
        await db.execute(select(func.count(Organization.id)).where(Organization.is_active.is_(True)))
    ).scalar_one()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total_messages_today = (
        await db.execute(select(func.count(Message.id)).where(Message.created_at >= today_start))
    ).scalar_one()

    total_escalations_pending = (
        await db.execute(
            select(func.count(Escalation.id)).where(Escalation.status == EscalationStatus.pending)
        )
    ).scalar_one()

    recent_activity = (
        (
            await db.execute(
                select(AuditLog)
                .where(AuditLog.target_type == "organization")
                .order_by(AuditLog.created_at.desc())
                .limit(10)
            )
        )
        .scalars()
        .all()
    )

    return {
        "total_orgs": total_orgs,
        "active_orgs": active_orgs,
        "total_messages_today": total_messages_today,
        "total_escalations_pending": total_escalations_pending,
        "recent_activity": [
            {
                "action": entry.action,
                "target_id": entry.target_id,
                "user_id": entry.user_id,
                "details": entry.details,
                "created_at": entry.created_at,
            }
            for entry in recent_activity
        ],
    }


async def get_org_dashboard_stats(db: AsyncSession, org_id: uuid.UUID) -> dict:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    messages_today = (
        await db.execute(
            select(func.count(Message.id)).where(Message.org_id == org_id, Message.created_at >= today_start)
        )
    ).scalar_one()

    open_escalations = (
        await db.execute(
            select(func.count(Escalation.id)).where(
                Escalation.org_id == org_id, Escalation.status != EscalationStatus.resolved
            )
        )
    ).scalar_one()

    now = datetime.now(timezone.utc)
    upcoming_appointments_24h = (
        await db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.org_id == org_id,
                Appointment.start_time >= now,
                Appointment.start_time <= now + timedelta(hours=24),
                Appointment.status != AppointmentStatus.cancelled,
            )
        )
    ).scalar_one()

    active_conversations = (
        await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.org_id == org_id, Conversation.status == ConversationStatus.active
            )
        )
    ).scalar_one()

    recent_rows = (
        await db.execute(
            select(Conversation, Contact.name)
            .join(Contact, Contact.id == Conversation.contact_id)
            .where(Conversation.org_id == org_id)
            .order_by(Conversation.last_message_at.desc())
            .limit(10)
        )
    ).all()

    return {
        "messages_today": messages_today,
        "open_escalations": open_escalations,
        "upcoming_appointments_24h": upcoming_appointments_24h,
        "active_conversations": active_conversations,
        "recent_conversations": [
            {
                "id": conversation.id,
                "contact_name": contact_name,
                "channel": conversation.channel.value,
                "status": conversation.status.value,
                "last_message_at": conversation.last_message_at,
            }
            for conversation, contact_name in recent_rows
        ],
    }
