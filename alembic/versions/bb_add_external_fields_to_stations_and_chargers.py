"""Add external identifier and raw_data fields to stations and chargers

Revision ID: bb_add_external_fields
Revises: aa1b2c3d4e5f
Create Date: 2025-10-17 12:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'bb_add_external_fields'
down_revision: Union[str, Sequence[str], None] = 'aa1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # stations: add external_bid, external_cp_id, raw_data(json), last_synced_at
    op.add_column('stations', sa.Column('external_bid', sa.String(length=50), nullable=True))
    op.add_column('stations', sa.Column('external_cp_id', sa.String(length=50), nullable=True))
    op.add_column('stations', sa.Column('raw_data', sa.JSON(), nullable=True))
    op.add_column('stations', sa.Column('last_synced_at', sa.DateTime(), nullable=True))

    # chargers: add external_charger_id, manufacturer, model, connector_types(json)
    op.add_column('chargers', sa.Column('external_charger_id', sa.String(length=50), nullable=True))
    op.add_column('chargers', sa.Column('manufacturer', sa.String(length=100), nullable=True))
    op.add_column('chargers', sa.Column('model', sa.String(length=100), nullable=True))
    op.add_column('chargers', sa.Column('connector_types', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('chargers', 'connector_types')
    op.drop_column('chargers', 'model')
    op.drop_column('chargers', 'manufacturer')
    op.drop_column('chargers', 'external_charger_id')

    op.drop_column('stations', 'last_synced_at')
    op.drop_column('stations', 'raw_data')
    op.drop_column('stations', 'external_cp_id')
    op.drop_column('stations', 'external_bid')
