"""Enable PostGIS extension and ensure GiST index on stations.location

Revision ID: aa1b2c3d4e5f
Revises: 60afb71f58fe
Create Date: 2025-10-17 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'aa1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '60afb71f58fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create PostGIS extension if not present
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # Ensure stations.location column exists as geometry(Point,4326) - if created earlier this is a no-op
    # Create GiST index on location if not exists
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='idx_stations_location') THEN
            CREATE INDEX idx_stations_location ON stations USING gist(location);
        END IF;
    END$$;
    """)


def downgrade() -> None:
    # Do not drop the postgis extension on downgrade to avoid removing shared functionality
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_class WHERE relname='idx_stations_location') THEN
            DROP INDEX idx_stations_location;
        END IF;
    END$$;
    """)
