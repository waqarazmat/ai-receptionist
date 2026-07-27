"""supported_languages

Revision ID: e5d8c2a1f6b3
Revises: f3a1b9c4e2d7
Create Date: 2026-07-27 00:00:00.000000

Adds organizations.supported_languages — a JSONB list of ISO 639-1 language
codes that the org's Retell voice agent presents to callers as a selection
menu.  Defaults to ["en"] so every existing org keeps English-only behaviour
without any data migration.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5d8c2a1f6b3"
down_revision: Union[str, None] = "f3a1b9c4e2d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "supported_languages",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default='["en"]',
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "supported_languages")
