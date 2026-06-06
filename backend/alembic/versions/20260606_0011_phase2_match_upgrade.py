"""Phase 2 Block H: add matching_mode to match_cache, recreate IVFFlat index.

Revision ID: 20260606_0011
Revises: 20260520_0010
Create Date: 2026-06-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260606_0011"
down_revision: str | Sequence[str] | None = "20260520_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add matching_mode with default so all existing rows get 'heuristic'
    op.add_column(
        "match_cache",
        sa.Column(
            "matching_mode",
            sa.Text(),
            nullable=False,
            server_default="heuristic",
        ),
    )
    op.create_check_constraint(
        "ck_match_cache_mode",
        "match_cache",
        "matching_mode IN ('heuristic', 'semantic')",
    )

    # Recreate IVFFlat index on user_embeddings(embedding) WHERE service='combined'.
    # Was intentionally dropped in migration 0010 to allow Block H to set lists=100
    # based on expected user volume at production scale.
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_embeddings_combined
        ON user_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        WHERE service = 'combined'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_user_embeddings_combined")
    op.drop_constraint("ck_match_cache_mode", "match_cache", type_="check")
    op.drop_column("match_cache", "matching_mode")
