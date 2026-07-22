"""add org billing plan

Revision ID: b2e0f3c1d8a4
Revises: a1f2c9b3e7d0
Create Date: 2026-07-22 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2e0f3c1d8a4'
down_revision: Union[str, None] = 'a1f2c9b3e7d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ENUM must be CREATE'd separately in Postgres; the server_default on the
    # column then references it. Doing this manually (rather than
    # sa.Enum.create()) gives us control over the type name.
    op.execute(
        "CREATE TYPE billing_plan AS ENUM ('free', 'starter', 'pro', 'enterprise')"
    )
    op.add_column(
        "organizations",
        sa.Column(
            "plan",
            sa.Enum("free", "starter", "pro", "enterprise", name="billing_plan"),
            nullable=False,
            server_default="free",
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "plan")
    op.execute("DROP TYPE billing_plan")
