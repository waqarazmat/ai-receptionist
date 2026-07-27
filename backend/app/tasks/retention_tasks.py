"""Scheduled task: prune conversations and messages older than each org's
retention window (Organization.data_retention_days, or the global default).

Runs nightly. Deletes Message rows first (FK child), then Conversation rows.
Escalations and Appointments that reference the deleted conversations are
also cleaned up — they hold no independent value once the conversation is gone.

Only resolved conversations are pruned — active or escalated conversations are
retained regardless of age so staff are not surprised by disappearing threads.
"""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import async_session_maker
from app.models.appointment import Appointment
from app.models.conversation import Conversation
from app.models.enums import ConversationStatus
from app.models.escalation import Escalation
from app.models.message import Message
from app.models.organization import Organization

logger = structlog.get_logger()


async def _prune_org(db: AsyncSession, org: Organization, cutoff: datetime) -> int:
    """Delete resolved conversations (and their children) older than cutoff.
    Returns the number of conversations deleted."""
    old_convs = (
        await db.execute(
            select(Conversation.id).where(
                Conversation.org_id == org.id,
                Conversation.status == ConversationStatus.resolved,
                Conversation.last_message_at < cutoff,
            )
        )
    ).scalars().all()

    if not old_convs:
        return 0

    conv_ids = list(old_convs)

    # Delete children before conversations (FK order)
    await db.execute(delete(Escalation).where(Escalation.conversation_id.in_(conv_ids)))
    await db.execute(delete(Appointment).where(Appointment.conversation_id.in_(conv_ids)))
    await db.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
    await db.execute(delete(Conversation).where(Conversation.id.in_(conv_ids)))

    await db.commit()
    return len(conv_ids)


async def prune_old_conversations(ctx: dict) -> None:
    """Arq cron job — runs once per day, prunes per-org retention windows."""
    now = datetime.now(timezone.utc)
    total_pruned = 0

    async with async_session_maker() as db:
        orgs = (await db.execute(select(Organization).where(Organization.is_active.is_(True)))).scalars().all()

    for org in orgs:
        retention_days = org.data_retention_days or settings.DEFAULT_CONVERSATION_RETENTION_DAYS
        cutoff = now - timedelta(days=retention_days)

        async with async_session_maker() as db:
            try:
                pruned = await _prune_org(db, org, cutoff)
                if pruned:
                    logger.info(
                        "retention_prune_complete",
                        org_id=str(org.id),
                        retention_days=retention_days,
                        conversations_deleted=pruned,
                    )
                total_pruned += pruned
            except Exception:  # noqa: BLE001 — one bad org must not block others
                logger.exception("retention_prune_failed", org_id=str(org.id))

    logger.info("retention_prune_run_complete", total_conversations_deleted=total_pruned)
