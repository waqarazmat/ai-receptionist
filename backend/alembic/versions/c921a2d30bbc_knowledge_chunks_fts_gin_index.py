"""knowledge chunks fts gin index

Revision ID: c921a2d30bbc
Revises: 8dd812fcd5b9
Create Date: 2026-07-10 18:23:06.739516

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c921a2d30bbc'
down_revision: Union[str, None] = '8dd812fcd5b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Functional GIN index accelerating the sparse (full-text) half of RAG's
    # hybrid_search. The expression MUST match the query's exactly —
    # to_tsvector('english', content) — or the planner won't use it. Without
    # this the FTS query is a sequential scan; with it, lookups stay flat as
    # knowledge bases grow. Read-path only: the vector half already has an HNSW
    # index (knowledge_chunks_embedding_idx). Plain (non-CONCURRENT) CREATE so
    # it runs inside Alembic's transaction — fine for these table sizes.
    op.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_chunks_content_fts_idx "
        "ON knowledge_chunks USING gin (to_tsvector('english', content))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS knowledge_chunks_content_fts_idx")
