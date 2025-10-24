"""Add API-compatible station columns and backfill from existing fields/location

Revision ID: 20251025_add_station_api_compat
Revises: 20251023_add_additional_kepco_fields
Create Date: 2025-10-25 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence

# revision identifiers, used by Alembic.
revision: str = '20251025_add_station_api_compat'
down_revision: Union[str, Sequence[str], None] = '20251023_add_additional_kepco_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure API-compatible columns exist (safe: IF NOT EXISTS)
    op.execute("ALTER TABLE stations ADD COLUMN IF NOT EXISTS cs_nm VARCHAR(200);")
    op.execute("ALTER TABLE stations ADD COLUMN IF NOT EXISTS addr TEXT;")
    op.execute("ALTER TABLE stations ADD COLUMN IF NOT EXISTS lat VARCHAR(32);")
    op.execute("ALTER TABLE stations ADD COLUMN IF NOT EXISTS longi VARCHAR(32);")

    # Backfill from existing data: name/address and PostGIS location -> lat/long
    # Use UPDATE only where columns are null or empty to avoid overwriting intentional values
    op.execute("""
        UPDATE stations
        SET cs_nm = COALESCE(cs_nm, name),
            addr = COALESCE(addr, address),
            lat = COALESCE(lat, ST_Y(location)::text),
            longi = COALESCE(longi, ST_X(location)::text)
        WHERE COALESCE(cs_nm,'') = '' OR COALESCE(lat,'') = '' OR COALESCE(longi,'') = '' OR COALESCE(addr,'') = '';
    """)

    # Add indexes for faster lookup by KEPCO id / address
    op.execute("CREATE INDEX IF NOT EXISTS ix_stations_cs_id ON stations (cs_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_stations_addr ON stations (addr);")


def downgrade() -> None:
    # Drop indexes (if they were created by this migration)
    op.execute("DROP INDEX IF EXISTS ix_stations_addr;")
    op.execute("DROP INDEX IF EXISTS ix_stations_cs_id;")

    # Remove API-compatible columns (safe: IF EXISTS)
    op.execute("ALTER TABLE stations DROP COLUMN IF EXISTS longi;")
    op.execute("ALTER TABLE stations DROP COLUMN IF EXISTS lat;")
    op.execute("ALTER TABLE stations DROP COLUMN IF EXISTS addr;")
    op.execute("ALTER TABLE stations DROP COLUMN IF EXISTS cs_nm;")
