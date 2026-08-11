"""Delete conversations + messages created by the load test for ONE org.

The harness creates a fresh "Web Visitor" contact + conversation per connection,
so a run leaves many rows behind. If the backend under test points at a shared
database (e.g. DATABASE_URL is the prod Railway Postgres), run this afterwards to
purge them. It ONLY touches the org id you pass — nothing else.

    python loadtest/cleanup.py <ORG_ID>
"""

import asyncio
import sys
import uuid

from sqlalchemy import delete, select

from app.db.engine import async_session_maker
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.message import Message


async def main(org_id: uuid.UUID):
    async with async_session_maker() as db:
        convo_ids = (await db.execute(
            select(Conversation.id).where(Conversation.org_id == org_id)
        )).scalars().all()
        contact_ids = (await db.execute(
            select(Contact.id).where(Contact.org_id == org_id, Contact.name == "Web Visitor")
        )).scalars().all()

        msgs = 0
        if convo_ids:
            res = await db.execute(delete(Message).where(Message.conversation_id.in_(convo_ids)))
            msgs = res.rowcount or 0
        convos = (await db.execute(
            delete(Conversation).where(Conversation.org_id == org_id)
        )).rowcount or 0
        contacts = 0
        if contact_ids:
            contacts = (await db.execute(
                delete(Contact).where(Contact.id.in_(contact_ids))
            )).rowcount or 0
        await db.commit()
        print(f"Deleted {msgs} messages, {convos} conversations, {contacts} 'Web Visitor' contacts "
              f"for org {org_id}.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python loadtest/cleanup.py <ORG_ID>")
        raise SystemExit(1)
    asyncio.run(main(uuid.UUID(sys.argv[1])))
