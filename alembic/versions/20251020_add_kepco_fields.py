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
    op.add_column('stations', sa.Column('cs_id', sa.String(length=50), nullable=True))
    op.add_column('chargers', sa.Column('cp_stat_raw', sa.String(length=20), nullable=True))
    op.add_column('chargers', sa.Column('stat_update_datetime', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('chargers', 'stat_update_datetime')
    op.drop_column('chargers', 'cp_stat_raw')
    op.drop_column('stations', 'cs_id')
