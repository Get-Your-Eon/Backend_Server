"""Add location column to chargers

Revision ID: c1d2e3f4add
Revises: bb_add_external_fields
Create Date: 2025-10-19 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4add'
down_revision: Union[str, Sequence[str], None] = 'bb_add_external_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add geometry location column to chargers if not exists
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='chargers' AND column_name='location'
        ) THEN
            ALTER TABLE chargers ADD COLUMN location geometry(POINT,4326);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='idx_chargers_location') THEN
            CREATE INDEX idx_chargers_location ON chargers USING gist(location);
        END IF;
    END$$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS chargers DROP COLUMN IF EXISTS location;")
    op.execute("DROP INDEX IF EXISTS idx_chargers_location;")
