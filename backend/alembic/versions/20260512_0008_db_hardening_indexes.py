"""DB hardening indexes: match_cache computed_at, obsessions item, overrides item, sync_status.

Revision ID: 20260512_0008
Revises: 20260503_0007
Create Date: 2026-05-12

Covers D1, D5, D6, D12 from the fix/db-hardening sprint:
  D1  — idx_match_cache_computed_at: range scan for the hourly cleanup job
  D5  — idx_obsessions_item: partial index for item_id FK (WHERE item_id IS NOT NULL)
  D6  — idx_overrides_item: item_id FK lookups in preference_overrides
  D12 — idx_sync_status: partial index for active/errored sync background queries
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260512_0008"
down_revision = "20260503_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # D1 — hourly cleanup job scans match_cache by computed_at
    op.create_index(
        "idx_match_cache_computed_at",
        "match_cache",
        ["computed_at"],
    )

    # D5 — item_id FK on manual_obsessions (partial: only rows that reference an item)
    op.create_index(
        "idx_obsessions_item",
        "manual_obsessions",
        ["item_id"],
        postgresql_where=sa.text("item_id IS NOT NULL"),
    )

    # D6 — item_id FK on preference_overrides
    op.create_index(
        "idx_overrides_item",
        "preference_overrides",
        ["item_id"],
    )

    # D12 — partial index for background queries on active/errored syncs
    op.create_index(
        "idx_sync_status",
        "service_connections",
        ["sync_status"],
        postgresql_where=sa.text("sync_status IN ('syncing', 'error')"),
    )


def downgrade() -> None:
    op.drop_index("idx_sync_status", table_name="service_connections")
    op.drop_index("idx_overrides_item", table_name="preference_overrides")
    op.drop_index("idx_obsessions_item", table_name="manual_obsessions")
    op.drop_index("idx_match_cache_computed_at", table_name="match_cache")
