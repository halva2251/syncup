"""add highlights column to match_cache

Revision ID: 20260502_0004
Revises: 20260502_0003
Create Date: 2026-05-02
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260502_0004"
down_revision: str | None = "20260502_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "match_cache",
        sa.Column(
            "highlights",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("match_cache", "highlights")
