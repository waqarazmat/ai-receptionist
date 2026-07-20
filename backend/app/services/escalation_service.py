import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.enums import EscalationStatus
from app.models.escalation import Escalation


class EscalationNotFoundError(Exception):
    pass


async def list_escalations(db: AsyncSession, org_id: uuid.UUID) -> list[Escalation]:
    stmt = (
        select(Escalation, Contact.name)
        .join(Conversation, Conversation.id == Escalation.conversation_id)
        .join(Contact, Contact.id == Conversation.contact_id)
        .where(Escalation.org_id == org_id, Escalation.status != EscalationStatus.resolved)
        .order_by(Escalation.created_at.desc())
    )
    result = await db.execute(stmt)
    escalations = []
    for escalation, contact_name in result.all():
        escalation.contact_name = contact_name
        escalations.append(escalation)
    return escalations


async def pick_up_escalation(
    db: AsyncSession, org_id: uuid.UUID, escalation_id: uuid.UUID, user_id: uuid.UUID
) -> Escalation:
    escalation = await db.get(Escalation, escalation_id)
    if escalation is None or escalation.org_id != org_id:
        raise EscalationNotFoundError(str(escalation_id))

    escalation.status = EscalationStatus.picked_up
    escalation.assigned_to = user_id

    conversation = await db.get(Conversation, escalation.conversation_id)
    if conversation is not None:
        conversation.assigned_to = user_id

    await db.commit()
    await db.refresh(escalation)

    from app.realtime.events import notify_escalation_picked_up

    await notify_escalation_picked_up(org_id, escalation_id, escalation.conversation_id)

    contact_name = ""
    if conversation is not None:
        contact = await db.get(Contact, conversation.contact_id)
        contact_name = contact.name if contact else ""
    escalation.contact_name = contact_name

    return escalation
