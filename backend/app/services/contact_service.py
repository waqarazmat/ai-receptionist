import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.enums import Channel


class ContactNotFoundError(Exception):
    pass


async def get_or_create_contact_by_phone(
    db: AsyncSession, org_id: uuid.UUID, phone: str, channel: Channel, name: str | None = None
) -> Contact:
    """WhatsApp and voice both have no session/auth concept like webchat —
    every inbound webhook/call is stateless, so the phone number is the
    identity to match an existing contact against. Scoped per-org AND
    per-channel: Contact.channel is a single non-null column, so the same
    phone number calling in on voice and messaging on WhatsApp is
    deliberately two separate Contact rows, not one shared across channels."""
    contact = (
        await db.execute(
            select(Contact).where(Contact.org_id == org_id, Contact.phone == phone, Contact.channel == channel)
        )
    ).scalars().first()
    if contact is not None:
        return contact

    contact = Contact(org_id=org_id, name=name or phone, phone=phone, channel=channel)
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


# Deliberately builds plain dicts rather than returning Contact ORM instances
# with a bolted-on `conversation_count` — that name collides with a REAL
# mapped column on Contact (currently unmaintained, always 0). Setting it as
# a plain attribute would mark the instance dirty and risk silently
# persisting the wrong value on any later flush/commit in the same session.


def _conversation_count_subquery():
    return (
        select(func.count(Conversation.id))
        .where(Conversation.contact_id == Contact.id)
        .correlate(Contact)
        .scalar_subquery()
    )


def _last_contact_at_subquery():
    return (
        select(func.max(Conversation.last_message_at))
        .where(Conversation.contact_id == Contact.id)
        .correlate(Contact)
        .scalar_subquery()
    )


def _to_dict(contact: Contact, conversation_count: int, last_contact_at) -> dict:
    return {
        "id": contact.id,
        "org_id": contact.org_id,
        "name": contact.name,
        "phone": contact.phone,
        "email": contact.email,
        "channel": contact.channel.value,
        "conversation_count": conversation_count or 0,
        "last_contact_at": last_contact_at,
    }


async def list_contacts(db: AsyncSession, org_id: uuid.UUID, search: str | None = None) -> list[dict]:
    stmt = select(Contact, _conversation_count_subquery(), _last_contact_at_subquery()).where(
        Contact.org_id == org_id
    )
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(or_(Contact.name.ilike(pattern), Contact.phone.ilike(pattern), Contact.email.ilike(pattern)))
    stmt = stmt.order_by(_last_contact_at_subquery().desc().nullslast())

    result = await db.execute(stmt)
    return [_to_dict(contact, count, last) for contact, count, last in result.all()]


async def get_contact(db: AsyncSession, org_id: uuid.UUID, contact_id: uuid.UUID) -> dict:
    contact = await db.get(Contact, contact_id)
    if contact is None or contact.org_id != org_id:
        raise ContactNotFoundError(str(contact_id))

    conversations = (
        await db.execute(
            select(Conversation)
            .where(Conversation.contact_id == contact_id)
            .order_by(Conversation.last_message_at.desc())
        )
    ).scalars().all()

    data = _to_dict(
        contact,
        len(conversations),
        conversations[0].last_message_at if conversations else None,
    )
    data["conversations"] = [
        {
            "id": conv.id,
            "channel": conv.channel.value,
            "status": conv.status.value,
            "last_message_at": conv.last_message_at,
        }
        for conv in conversations
    ]
    return data
