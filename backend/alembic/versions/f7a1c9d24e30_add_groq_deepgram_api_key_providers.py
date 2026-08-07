"""add groq and deepgram api key providers

Enables per-org (tenant-isolated) storage of the voice-note pipeline's STT
(groq) and TTS (deepgram) keys in org_api_keys, alongside the existing LLM /
whatsapp / retell providers. openai is already a provider value and is reused
for OpenAI TTS.

Revision ID: f7a1c9d24e30
Revises: e5d8c2a1f6b3
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f7a1c9d24e30'
down_revision: Union[str, None] = 'e5d8c2a1f6b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Native Postgres enum values aren't diffed by alembic autogenerate — add
    # them manually (idempotent), same pattern as the retell provider addition.
    op.execute("ALTER TYPE api_key_provider ADD VALUE IF NOT EXISTS 'groq'")
    op.execute("ALTER TYPE api_key_provider ADD VALUE IF NOT EXISTS 'deepgram'")


def downgrade() -> None:
    # Postgres has no ALTER TYPE ... DROP VALUE — dropping an enum value needs a
    # full type rebuild, not warranted for a dev-time rollback. No-op, matching
    # how other enum additions in this project's migration history are handled.
    pass
