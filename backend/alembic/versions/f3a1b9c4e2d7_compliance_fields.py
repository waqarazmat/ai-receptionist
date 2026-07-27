"""compliance_fields

Revision ID: f3a1b9c4e2d7
Revises: b2e0f3c1d8a4
Create Date: 2026-07-24 00:00:00.000000

Adds three fields to organizations and one to conversations for
GDPR / AI Act compliance:

  organizations.business_vertical  — per-vertical guardrail routing + default retention
  organizations.data_retention_days — per-tenant GDPR retention window (NULL = global default)
  organizations.country             — ISO 3166-1 alpha-2 code (groundwork, no logic yet)
  conversations.ai_disclosure_sent_at — timestamp proving AI disclosure was delivered (Art. 50)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a1b9c4e2d7"
down_revision: Union[str, None] = "b2e0f3c1d8a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VERTICAL_ENUM = sa.Enum(
    "general", "medical", "dental", "veterinary", "legal",
    "gym", "salon", "spa", "real_estate", "other",
    name="business_vertical",
)


def upgrade() -> None:
    _VERTICAL_ENUM.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "organizations",
        sa.Column(
            "business_vertical",
            _VERTICAL_ENUM,
            nullable=False,
            server_default="general",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column("data_retention_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("country", sa.String(2), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "ai_disclosure_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "ai_disclosure_sent_at")
    op.drop_column("organizations", "country")
    op.drop_column("organizations", "data_retention_days")
    op.drop_column("organizations", "business_vertical")
    _VERTICAL_ENUM.drop(op.get_bind(), checkfirst=True)
