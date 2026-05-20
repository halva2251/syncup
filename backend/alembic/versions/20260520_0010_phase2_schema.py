"""Phase 2 Block A schema additions.

Revision ID: 20260520_0010
Revises: 20260512_0008
Create Date: 2026-05-20

Changes:
  - users: add vibe_summary, archetype, key_themes, vibe_computed_at (all nullable)
  - user_items: add excluded BOOLEAN NOT NULL DEFAULT FALSE
  - items.embedding: widen vector dimension 128 → 384 (sentence-transformers)
  - user_embeddings.embedding: widen vector dimension 128 → 384; delete stale rows first
  - Drop and recreate idx_items_embedding with new dimension
  - idx_user_embeddings_combined deferred to Block H (match upgrade)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260520_0010"
down_revision: str | Sequence[str] | None = "20260512_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. New nullable columns on users (safe on any table size) ─────────────
    op.add_column("users", sa.Column("vibe_summary", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("archetype", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("key_themes", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("vibe_computed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── 2. excluded column on user_items (NOT NULL + server_default — safe) ───
    op.add_column(
        "user_items",
        sa.Column(
            "excluded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # ── 3. Widen vector dimensions: 128 → 384 ─────────────────────────────────
    # IVFFlat index on items.embedding must be dropped before type change.
    op.drop_index("idx_items_embedding", table_name="items", if_exists=True)

    # Null out stale 128-dim item embeddings — they are incompatible with 384.
    # New embeddings will be populated by scripts/populate_item_embeddings.py.
    op.execute(sa.text("UPDATE items SET embedding = NULL WHERE embedding IS NOT NULL"))

    op.execute(sa.text("ALTER TABLE items ALTER COLUMN embedding TYPE vector(384)"))

    # user_embeddings.embedding is NOT NULL — delete stale rows before alter.
    # Rows will be rebuilt when users recompute via POST /api/embeddings/build.
    op.execute(sa.text("DELETE FROM user_embeddings"))
    op.execute(sa.text("ALTER TABLE user_embeddings ALTER COLUMN embedding TYPE vector(384)"))

    # Recreate items IVFFlat index with new dimension.
    # lists=100 is a reasonable placeholder; retune to sqrt(row_count) once
    # the items table is populated by the enrichment + embedding scripts.
    op.execute(
        sa.text(
            """
            CREATE INDEX idx_items_embedding
            ON items
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
            WHERE embedding IS NOT NULL
            """
        )
    )
    # Note: idx_user_embeddings_combined is deferred to Block H (match upgrade,
    # feat/phase2-match-upgrade). The index requires trained combined vectors
    # to be useful and its lists parameter needs to be tuned at that point.


def downgrade() -> None:
    # Drop recreated items index
    op.drop_index("idx_items_embedding", table_name="items", if_exists=True)

    # Revert items.embedding dimension
    op.execute(sa.text("UPDATE items SET embedding = NULL WHERE embedding IS NOT NULL"))
    op.execute(sa.text("ALTER TABLE items ALTER COLUMN embedding TYPE vector(128)"))

    # Revert user_embeddings.embedding dimension
    op.execute(sa.text("DELETE FROM user_embeddings"))
    op.execute(sa.text("ALTER TABLE user_embeddings ALTER COLUMN embedding TYPE vector(128)"))

    # Restore original items IVFFlat index (128-dim)
    op.execute(
        sa.text(
            """
            CREATE INDEX idx_items_embedding
            ON items
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
            WHERE embedding IS NOT NULL
            """
        )
    )

    # Remove added columns
    op.drop_column("user_items", "excluded")
    op.drop_column("users", "vibe_computed_at")
    op.drop_column("users", "key_themes")
    op.drop_column("users", "archetype")
    op.drop_column("users", "vibe_summary")
