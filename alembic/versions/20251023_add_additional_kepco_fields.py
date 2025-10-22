"""Add additional KEPCO fields for station/charger management

Revision ID: 20251023_add_additional_kepco_fields
Revises: d8c47bac145f
Create Date: 2025-10-23 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence

# revision identifiers, used by Alembic.
revision: str = '20251023_add_additional_kepco_fields'
down_revision: Union[str, Sequence[str], None] = 'd8c47bac145f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new KEPCO fields to stations table
    op.execute("ALTER TABLE stations ADD COLUMN IF NOT EXISTS cs_nm VARCHAR(200);")
    op.execute("ALTER TABLE stations ADD COLUMN IF NOT EXISTS addr TEXT;")
    op.execute("ALTER TABLE stations ADD COLUMN IF NOT EXISTS lat VARCHAR(20);")
    op.execute("ALTER TABLE stations ADD COLUMN IF NOT EXISTS longi VARCHAR(20);")
    op.execute("ALTER TABLE stations ADD COLUMN IF NOT EXISTS static_data_updated_at TIMESTAMP;")
    op.execute("ALTER TABLE stations ADD COLUMN IF NOT EXISTS dynamic_data_updated_at TIMESTAMP;")
    
    # Add indexes for performance
    op.execute("CREATE INDEX IF NOT EXISTS ix_stations_cs_id ON stations (cs_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_stations_addr ON stations (addr);")
    
    # Add new KEPCO fields to chargers table
    op.execute("ALTER TABLE chargers ADD COLUMN IF NOT EXISTS cp_id VARCHAR(50);")
    op.execute("ALTER TABLE chargers ADD COLUMN IF NOT EXISTS cp_nm VARCHAR(200);")
    op.execute("ALTER TABLE chargers ADD COLUMN IF NOT EXISTS charge_tp VARCHAR(10);")
    op.execute("ALTER TABLE chargers ADD COLUMN IF NOT EXISTS cp_tp VARCHAR(10);")
    op.execute("ALTER TABLE chargers ADD COLUMN IF NOT EXISTS cp_stat VARCHAR(10);")
    op.execute("ALTER TABLE chargers ADD COLUMN IF NOT EXISTS kepco_stat_update_datetime VARCHAR(50);")
    op.execute("ALTER TABLE chargers ADD COLUMN IF NOT EXISTS cs_id VARCHAR(50);")
    
    # Add indexes for performance
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_chargers_cp_id ON chargers (cp_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_chargers_cp_stat ON chargers (cp_stat);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_chargers_cs_id ON chargers (cs_id);")


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_chargers_cs_id;")
    op.execute("DROP INDEX IF EXISTS ix_chargers_cp_stat;")
    op.execute("DROP INDEX IF EXISTS ix_chargers_cp_id;")
    op.execute("DROP INDEX IF EXISTS ix_stations_addr;")
    op.execute("DROP INDEX IF EXISTS ix_stations_cs_id;")
    
    # Drop columns from chargers
    op.execute("ALTER TABLE chargers DROP COLUMN IF EXISTS cs_id;")
    op.execute("ALTER TABLE chargers DROP COLUMN IF EXISTS kepco_stat_update_datetime;")
    op.execute("ALTER TABLE chargers DROP COLUMN IF EXISTS cp_stat;")
    op.execute("ALTER TABLE chargers DROP COLUMN IF EXISTS cp_tp;")
    op.execute("ALTER TABLE chargers DROP COLUMN IF EXISTS charge_tp;")
    op.execute("ALTER TABLE chargers DROP COLUMN IF EXISTS cp_nm;")
    op.execute("ALTER TABLE chargers DROP COLUMN IF EXISTS cp_id;")
    
    # Drop columns from stations
    op.execute("ALTER TABLE stations DROP COLUMN IF EXISTS dynamic_data_updated_at;")
    op.execute("ALTER TABLE stations DROP COLUMN IF EXISTS static_data_updated_at;")
    op.execute("ALTER TABLE stations DROP COLUMN IF EXISTS longi;")
    op.execute("ALTER TABLE stations DROP COLUMN IF EXISTS lat;")
    op.execute("ALTER TABLE stations DROP COLUMN IF EXISTS addr;")
    op.execute("ALTER TABLE stations DROP COLUMN IF EXISTS cs_nm;")