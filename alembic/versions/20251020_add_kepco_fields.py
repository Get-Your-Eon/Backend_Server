"""Add Kepco-specific fields: stations.cs_id, chargers.cp_stat_raw, chargers.stat_update_datetime

Revision ID: 20251020_add_kepco_fields
Revises: bb_add_external_fields
Create Date: 2025-10-20 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence

# revision identifiers, used by Alembic.
revision: str = '20251020_add_kepco_fields'
down_revision: Union[str, Sequence[str], None] = 'bb_add_external_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
            # Execute single SQL statements separately because asyncpg prepared
            # statements do not accept multiple semicolon-separated commands.
            op.execute("ALTER TABLE stations ADD COLUMN IF NOT EXISTS cs_id VARCHAR(50);")
            op.execute(
                    "ALTER TABLE chargers ADD COLUMN IF NOT EXISTS cp_stat_raw VARCHAR(20), ADD COLUMN IF NOT EXISTS stat_update_datetime TIMESTAMP;"
            )


def downgrade() -> None:
    op.drop_column('chargers', 'stat_update_datetime')
    op.drop_column('chargers', 'cp_stat_raw')
    op.drop_column('stations', 'cs_id')
