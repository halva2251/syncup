"""Phase 2 Block I: switch idx_items_embedding from IVFFlat to HNSW.

IVFFlat with lists=100 requires ivfflat.probes to be tuned for recall —
the PostgreSQL default of 1 probe searches only 1% of the catalog.
HNSW has no probes parameter, handles dynamic inserts gracefully, and
is already the project standard for user_embeddings (migration 0011).

Revision ID: 20260606_0012
Revises: 20260606_0011
Create Date: 2026-06-06
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260606_0012"
down_revision: str | Sequence[str] | None = "20260606_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_items_embedding")
    op.execute(
        """
        CREATE INDEX idx_items_embedding
        ON items
        USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_items_embedding")
    op.execute(
        """
        CREATE INDEX idx_items_embedding
        ON items
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        WHERE embedding IS NOT NULL
        """
    )
