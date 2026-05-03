"""expand manual_obsessions category check constraint

Revision ID: 20260503_0007
Revises: 20260503_0006
Create Date: 2026-05-03

Adds 'anime', 'manga', 'community' to the allowed category values to
support AniList and Reddit ingest (Phase 1.10).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260503_0007"
down_revision: str | None = "20260503_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_CONSTRAINT = "ck_obsession_category_values"
_OLD_VALUES = "('game', 'music', 'film', 'book', 'show', 'other')"
_NEW_VALUES = "('game', 'music', 'film', 'book', 'show', 'anime', 'manga', 'community', 'other')"


def upgrade() -> None:
    op.drop_constraint(_OLD_CONSTRAINT, "manual_obsessions", type_="check")
    op.create_check_constraint(
        _OLD_CONSTRAINT,
        "manual_obsessions",
        f"category IN {_NEW_VALUES}",
    )


def downgrade() -> None:
    op.drop_constraint(_OLD_CONSTRAINT, "manual_obsessions", type_="check")
    op.create_check_constraint(
        _OLD_CONSTRAINT,
        "manual_obsessions",
        f"category IN {_OLD_VALUES}",
    )
