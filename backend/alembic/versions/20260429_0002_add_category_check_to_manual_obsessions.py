"""add category check constraint to manual_obsessions

Revision ID: 20260429_0002
Revises: 20260421_0001
Create Date: 2026-04-29
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260429_0002"
down_revision: str | None = "20260421_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_obsession_category_values",
        "manual_obsessions",
        "category IN ('game', 'music', 'film', 'book', 'show', 'other')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_obsession_category_values", "manual_obsessions", type_="check"
    )
