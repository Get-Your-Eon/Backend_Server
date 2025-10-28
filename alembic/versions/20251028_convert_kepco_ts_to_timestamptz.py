"""Convert chargers.kepco_stat_update_datetime from varchar to timestamptz (UTC)

Revision ID: 20251028_convert_kepco_ts_to_timestamptz
Revises: 20251025_add_cp_fields_migration
Create Date: 2025-10-28 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence

# revision identifiers, used by Alembic.
revision: str = '20251028_convert_kepco_ts_to_timestamptz'
down_revision: Union[str, Sequence[str], None] = '20251025_add_cp_fields_migration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add a temporary timestamptz column
    op.execute("ALTER TABLE chargers ADD COLUMN IF NOT EXISTS kepco_stat_update_datetime_tz TIMESTAMPTZ;")

    # Best-effort conversion from existing varchar formats to timestamptz (assume UTC when timezone missing)
    # Handles common compact format YYYYMMDDHH24MISS and ISO-like strings. Non-parseable values will be left NULL.
    op.execute(r"""
    UPDATE chargers
    SET kepco_stat_update_datetime_tz = (
        CASE
            WHEN kepco_stat_update_datetime IS NULL OR trim(kepco_stat_update_datetime) = '' THEN NULL
            WHEN kepco_stat_update_datetime ~ '^[0-9]{14}$' THEN to_timestamp(kepco_stat_update_datetime, 'YYYYMMDDHH24MISS') AT TIME ZONE 'UTC'
            ELSE (
                -- try casting ISO-like string; if no timezone present we append 'Z' to assume UTC
                CASE
                    WHEN kepco_stat_update_datetime ~ '[+-][0-9]{2}(:?[0-9]{2})?$' THEN (kepco_stat_update_datetime)::timestamptz
                    WHEN kepco_stat_update_datetime ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$' THEN (kepco_stat_update_datetime || 'Z')::timestamptz
                    ELSE NULL
                END
            )
        END
    )
    WHERE kepco_stat_update_datetime IS NOT NULL;
    """)

    # If conversion created values, drop old column and rename
    op.execute("ALTER TABLE chargers DROP COLUMN IF EXISTS kepco_stat_update_datetime;")
    op.execute("ALTER TABLE chargers RENAME COLUMN kepco_stat_update_datetime_tz TO kepco_stat_update_datetime;")


def downgrade() -> None:
    # Recreate varchar column and populate with ISO strings from timestamptz
    op.execute("ALTER TABLE chargers ADD COLUMN IF NOT EXISTS kepco_stat_update_datetime_varchar VARCHAR(50);")
    op.execute(r"""
    UPDATE chargers
    SET kepco_stat_update_datetime_varchar = (
        CASE
            WHEN kepco_stat_update_datetime IS NULL THEN NULL
            ELSE to_char(kepco_stat_update_datetime AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
        END
    );
    """)
    op.execute("ALTER TABLE chargers DROP COLUMN IF EXISTS kepco_stat_update_datetime;")
    op.execute("ALTER TABLE chargers RENAME COLUMN kepco_stat_update_datetime_varchar TO kepco_stat_update_datetime;")