"""Delete conversations + messages created by the load test for ONE org.

The harness creates a fresh "Web Visitor" contact + conversation per connection,
so a run leaves many rows behind. If the backend under test points at a shared
database (e.g. DATABASE_URL is the prod Railway Postgres), run this afterwards to
purge them.

SAFETY: this deletes ONLY conversations that belong to a "Web Visitor" contact
(the anonymous contact the harness/widget creates) — never a real named contact's
conversations. So it is safe to run even against an org that also has real chat
history. It still won't distinguish a genuine anonymous widget visitor from a
harness one, so prefer a dedicated test org, or pass --since to limit by age.

    python loadtest/cleanup.py <ORG_ID> [--since-minutes N]
"""

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.db.engine import async_session_maker
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.message import Message


async def main(org_id: uuid.UUID, since_minutes: int | None = None):
    async with async_session_maker() as db:
        # Only the anonymous harness/widget contacts — never real named contacts.
        contact_q = select(Contact.id).where(
            Contact.org_id == org_id, Contact.name == "Web Visitor"
        )
        if since_minutes is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
            contact_q = contact_q.where(Contact.created_at >= cutoff)
        contact_ids = (await db.execute(contact_q)).scalars().all()

        if not contact_ids:
            print(f"No 'Web Visitor' contacts to clean up for org {org_id}.")
            return

        # Scope conversation/message deletion to those contacts ONLY — this is the
        # key difference from a blanket org-wide delete: real conversations stay.
        convo_ids = (await db.execute(
            select(Conversation.id).where(
                Conversation.org_id == org_id,
                Conversation.contact_id.in_(contact_ids),
            )
        )).scalars().all()

        msgs = 0
        if convo_ids:
            msgs = (await db.execute(
                delete(Message).where(Message.conversation_id.in_(convo_ids))
            )).rowcount or 0
            await db.execute(delete(Conversation).where(Conversation.id.in_(convo_ids)))
        contacts = (await db.execute(
            delete(Contact).where(Contact.id.in_(contact_ids))
        )).rowcount or 0
        await db.commit()
        print(f"Deleted {msgs} messages, {len(convo_ids)} conversations, {contacts} "
              f"'Web Visitor' contacts for org {org_id}.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python loadtest/cleanup.py <ORG_ID> [--since-minutes N]")
        raise SystemExit(1)
    since = None
    if "--since-minutes" in sys.argv:
        since = int(sys.argv[sys.argv.index("--since-minutes") + 1])
    asyncio.run(main(uuid.UUID(sys.argv[1]), since))
