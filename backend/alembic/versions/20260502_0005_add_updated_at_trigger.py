"""add updated_at trigger for users table

Ensures updated_at is always refreshed on any UPDATE, including raw
execute() statements that bypass SQLAlchemy's onupdate mechanism.

Revision ID: 20260502_0005
Revises: 20260502_0004
Create Date: 2026-05-02
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260502_0005"
down_revision: str | None = "20260502_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION update_users_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION update_users_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_users_updated_at ON users;")
    op.execute("DROP FUNCTION IF EXISTS update_users_updated_at;")
