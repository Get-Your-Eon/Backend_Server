from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = '60afb71f58fe'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema safely."""
    conn = op.get_bind()

    # api_logs 테이블 생성
    conn.execute("""
    CREATE TABLE IF NOT EXISTS api_logs (
        id SERIAL PRIMARY KEY,
        endpoint VARCHAR,
        method VARCHAR,
        api_type VARCHAR(50),
        request_time TIMESTAMP NOT NULL,
        status_code INTEGER,
        response_code INTEGER,
        response_msg TEXT,
        response_time_ms FLOAT
    );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_api_logs_id ON api_logs(id);")

    # stations 테이블 생성
    conn.execute("""
    CREATE TABLE IF NOT EXISTS stations (
        id SERIAL PRIMARY KEY,
        station_code VARCHAR(50) NOT NULL UNIQUE,
        name VARCHAR(200) NOT NULL,
        address TEXT,
        location GEOMETRY(POINT, 4326),
        provider VARCHAR(100),
        created_at TIMESTAMP NOT NULL DEFAULT now(),
        updated_at TIMESTAMP NOT NULL DEFAULT now()
    );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_stations_station_code ON stations(station_code);")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_stations_id ON stations(id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stations_location ON stations USING gist(location);")

    # chargers 테이블 생성
    conn.execute("""
    CREATE TABLE IF NOT EXISTS chargers (
        id SERIAL PRIMARY KEY,
        station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
        charger_code VARCHAR(50),
        charger_type VARCHAR(50),
        output_kw NUMERIC(5,2),
        connector_type VARCHAR(50),
        status_code INTEGER,
        created_at TIMESTAMP NOT NULL DEFAULT now(),
        updated_at TIMESTAMP NOT NULL DEFAULT now()
    );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_chargers_id ON chargers(id);")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_chargers_station_id ON chargers(station_id);")


def downgrade() -> None:
    """Downgrade schema safely."""
    conn = op.get_bind()
    conn.execute("DROP TABLE IF EXISTS chargers CASCADE;")
    conn.execute("DROP TABLE IF EXISTS stations CASCADE;")
    conn.execute("DROP TABLE IF EXISTS api_logs CASCADE;")
