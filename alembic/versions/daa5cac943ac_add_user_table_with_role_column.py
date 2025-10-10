from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = 'daa5cac943ac'
down_revision: Union[str, Sequence[str], None] = '82564d70969d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema safely."""
    conn = op.get_bind()

    # api_logs 테이블 생성
    conn.execute("""
    CREATE TABLE IF NOT EXISTS api_logs (
        id SERIAL PRIMARY KEY,
        endpoint VARCHAR(255) NOT NULL,
        method VARCHAR(10) NOT NULL,
        api_type VARCHAR(50) NOT NULL,
        status_code INTEGER NOT NULL,
        response_code INTEGER,
        response_msg VARCHAR(255)
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
        provider VARCHAR(100),
        location GEOMETRY(POINT,4326),
        created_at TIMESTAMP NOT NULL DEFAULT now(),
        updated_at TIMESTAMP NOT NULL DEFAULT now()
    );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_stations_id ON stations(id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stations_location ON stations USING gist(location);")

    # subsidies 테이블 생성
    conn.execute("""
    CREATE TABLE IF NOT EXISTS subsidies (
        id SERIAL PRIMARY KEY,
        manufacturer VARCHAR NOT NULL,
        model_group VARCHAR NOT NULL,
        model_name VARCHAR NOT NULL UNIQUE,
        subsidy_national_10k_won INTEGER NOT NULL,
        subsidy_local_10k_won INTEGER NOT NULL,
        subsidy_total_10k_won INTEGER NOT NULL
    );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_subsidies_id ON subsidies(id);")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_subsidies_manufacturer ON subsidies(manufacturer);")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_subsidies_model_group ON subsidies(model_group);")

    # users 테이블 생성
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) NOT NULL UNIQUE,
        hashed_password VARCHAR(255) NOT NULL,
        role VARCHAR(20) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT now(),
        updated_at TIMESTAMP NOT NULL DEFAULT now()
    );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_users_id ON users(id);")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_users_role ON users(role);")

    # chargers 테이블 생성
    conn.execute("""
    CREATE TABLE IF NOT EXISTS chargers (
        id SERIAL PRIMARY KEY,
        station_id INTEGER NOT NULL REFERENCES stations(id),
        charger_code VARCHAR(50),
        charger_type VARCHAR(50),
        connector_type VARCHAR(50),
        output_kw FLOAT,
        status_code INTEGER,
        created_at TIMESTAMP NOT NULL DEFAULT now(),
        updated_at TIMESTAMP NOT NULL DEFAULT now(),
        UNIQUE(station_id, charger_code)
    );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_chargers_id ON chargers(id);")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_chargers_station_id ON chargers(station_id);")


def downgrade() -> None:
    """Downgrade schema safely."""
    conn = op.get_bind()
    conn.execute("DROP TABLE IF EXISTS chargers CASCADE;")
    conn.execute("DROP TABLE IF EXISTS users CASCADE;")
    conn.execute("DROP TABLE IF EXISTS subsidies CASCADE;")
    conn.execute("DROP TABLE IF EXISTS stations CASCADE;")
    conn.execute("DROP TABLE IF EXISTS api_logs CASCADE;")
