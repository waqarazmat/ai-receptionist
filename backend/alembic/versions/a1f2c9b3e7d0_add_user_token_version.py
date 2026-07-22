"""add user token_version

Revision ID: a1f2c9b3e7d0
Revises: c921a2d30bbc
Create Date: 2026-07-22 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f2c9b3e7d0'
down_revision: Union[str, None] = 'c921a2d30bbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOT NULL with server_default=1 covers existing rows in one shot — no
    # backfill pass needed. Every current refresh token gets version=1; the
    # first logout / deactivate bumps to 2 and instantly invalidates any
    # older token in circulation.
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
