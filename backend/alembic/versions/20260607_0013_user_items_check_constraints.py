"""add engagement_score CHECK constraint to user_items

Revision ID: 20260607_0013
Revises: 20260606_0012
Create Date: 2026-06-07

engagement_score is always clamped to [0, 1] in application code (see
syncup/api/routes/sync.py), so the DB should enforce that invariant too.

Note: ck_user_items_raw_type_values already exists in the DB (created by
migration 20260503_0006) — it was only missing from the ORM model
(__table_args__), which has been corrected separately. No migration needed
for it since the DB-level constraint was never dropped.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260607_0013"
down_revision: str | None = "20260606_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_user_items_engagement_score_range",
        "user_items",
        "engagement_score >= 0 AND engagement_score <= 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_items_engagement_score_range", "user_items", type_="check")
