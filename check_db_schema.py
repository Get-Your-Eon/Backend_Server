#!/usr/bin/env python3
"""Database schema inspection helper.

Connects to the configured database and prints column metadata for a
handful of tables used by the service. Intended for quick manual checks.
"""

import asyncio
import asyncpg
import os
from app.core.config import settings

async def check_db_schema():
    """Check table column metadata for important tables.

    Connects to the configured DATABASE_URL and prints column lists for
    `stations` and `chargers`, then prints the current alembic version.
    """
    try:
        # Connect to the database
        conn = await asyncpg.connect(settings.DATABASE_URL)

        print("stations table schema:")
        result = await conn.fetch(
            """
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'stations' 
            ORDER BY ordinal_position;
        """
        )

        for row in result:
            print(f"  - {row['column_name']}: {row['data_type']} ({'NULL' if row['is_nullable'] == 'YES' else 'NOT NULL'})")

        print("\nchargers table schema:")
        result = await conn.fetch(
            """
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'chargers' 
            ORDER BY ordinal_position;
        """
        )

        for row in result:
            print(f"  - {row['column_name']}: {row['data_type']} ({'NULL' if row['is_nullable'] == 'YES' else 'NOT NULL'})")

        print("\nalembic_version:")
        result = await conn.fetch("SELECT version_num FROM alembic_version;")
        if result:
            print(f"  current migration version: {result[0]['version_num']}")
        else:
            print("  no migration information found")

        await conn.close()

    except Exception as e:
        print(f"DB connection error: {e}")

if __name__ == "__main__":
    asyncio.run(check_db_schema())