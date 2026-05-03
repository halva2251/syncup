"""add raw_type column to user_items

Revision ID: 20260503_0006
Revises: 20260502_0005
Create Date: 2026-05-03

raw_type distinguishes consumption signals (hours, scrobble count) from
rating signals (star ratings). The embedding builder applies different
normalization for each. Values: 'consumption' | 'rating'.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260503_0006"
down_revision: str | None = "20260502_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_items",
        sa.Column(
            "raw_type",
            sa.Text(),
            nullable=False,
            server_default="consumption",
        ),
    )
    op.create_check_constraint(
        "ck_user_items_raw_type_values",
        "user_items",
        "raw_type IN ('consumption', 'rating')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_user_items_raw_type_values", "user_items", type_="check"
    )
    op.drop_column("user_items", "raw_type")
