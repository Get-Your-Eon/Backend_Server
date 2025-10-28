"""Ensure cp_id/cp_nm/cp_stat/charge_tp/cs_id exist on chargers (idempotent)

Revision ID: 20251025_add_cp_fields_migration
Revises: 20251023_add_additional_kepco_fields
Create Date: 2025-10-25 15:30:00.000000
"""
from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence

# revision identifiers, used by Alembic.
revision: str = '20251025_add_cp_fields_migration'
down_revision: Union[str, Sequence[str], None] = '20251023_add_additional_kepco_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns to chargers if they don't exist (safe / idempotent)
    op.execute("ALTER TABLE chargers ADD COLUMN IF NOT EXISTS cp_id VARCHAR(50);")
    op.execute("ALTER TABLE chargers ADD COLUMN IF NOT EXISTS cp_nm VARCHAR(200);")
    op.execute("ALTER TABLE chargers ADD COLUMN IF NOT EXISTS cp_stat VARCHAR(50);")
    op.execute("ALTER TABLE chargers ADD COLUMN IF NOT EXISTS charge_tp VARCHAR(50);")
    op.execute("ALTER TABLE chargers ADD COLUMN IF NOT EXISTS cs_id VARCHAR(50);")

    # Create unique index on cp_id to support ON CONFLICT upserts used by application
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_chargers_cp_id ON chargers (cp_id);")


def downgrade() -> None:
    # Downgrade should remove the columns and index if necessary
    op.execute("DROP INDEX IF EXISTS ix_chargers_cp_id;")
    op.execute("ALTER TABLE chargers DROP COLUMN IF EXISTS cs_id;")
    op.execute("ALTER TABLE chargers DROP COLUMN IF EXISTS charge_tp;")
    op.execute("ALTER TABLE chargers DROP COLUMN IF EXISTS cp_stat;")
    op.execute("ALTER TABLE chargers DROP COLUMN IF EXISTS cp_nm;")
    op.execute("ALTER TABLE chargers DROP COLUMN IF EXISTS cp_id;")
