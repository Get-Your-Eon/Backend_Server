"""Create station, charger, and api_log tables

Revision ID: 60afb71f58fe
Revises:
Create Date: 2025-10-05 17:43:12.671323
"""
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
    # api_logs 테이블 생성 (존재하지 않을 경우만)
    op.execute("""
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
    # api_logs 인덱스 안전하게 생성
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='ix_api_logs_id') THEN
            CREATE INDEX ix_api_logs_id ON api_logs(id);
        END IF;
    END$$;
    """)

    # stations 테이블 생성
    op.execute("""
    CREATE TABLE IF NOT EXISTS stations (
        id SERIAL PRIMARY KEY,
        station_code VARCHAR(50) NOT NULL,
        name VARCHAR(200) NOT NULL,
        address TEXT,
        location GEOMETRY(POINT, 4326),
        provider VARCHAR(100),
        created_at TIMESTAMP NOT NULL DEFAULT now(),
        updated_at TIMESTAMP NOT NULL DEFAULT now()
    );
    """)
    # stations 인덱스 안전하게 생성
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='ix_stations_station_code') THEN
            CREATE UNIQUE INDEX ix_stations_station_code ON stations(station_code);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='ix_stations_id') THEN
            CREATE INDEX ix_stations_id ON stations(id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='idx_stations_location') THEN
            CREATE INDEX idx_stations_location ON stations USING gist(location);
        END IF;
    END$$;
    """)

    # chargers 테이블 생성
    op.execute("""
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
    # chargers 인덱스 안전하게 생성
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='ix_chargers_id') THEN
            CREATE INDEX ix_chargers_id ON chargers(id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='ix_chargers_station_id') THEN
            CREATE INDEX ix_chargers_station_id ON chargers(station_id);
        END IF;
    END$$;
    """)


def downgrade() -> None:
    """Downgrade schema safely."""
    # 테이블 삭제 시 CASCADE 적용
    op.execute("DROP TABLE IF EXISTS chargers CASCADE;")
    op.execute("DROP TABLE IF EXISTS stations CASCADE;")
    op.execute("DROP TABLE IF EXISTS api_logs CASCADE;")
