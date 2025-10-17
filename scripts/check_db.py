"""Simple script to check whether the PostgreSQL database has initial data.

Usage:
  export DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
  python scripts/check_db.py
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text


async def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL environment variable is not set")
        return

    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        try:
            print("Checking tables: stations, chargers, subsidies...\n")
            q = text("SELECT count(*) FROM stations;")
            r = await conn.execute(q)
            stations_count = r.scalar_one_or_none()
            print(f"stations count: {stations_count}")
        except Exception as e:
            print(f"Error checking stations: {e}")

        try:
            q = text("SELECT count(*) FROM chargers;")
            r = await conn.execute(q)
            print(f"chargers count: {r.scalar_one_or_none()}")
        except Exception as e:
            print(f"Error checking chargers: {e}")

        try:
            q = text("SELECT count(*) FROM subsidies;")
            r = await conn.execute(q)
            print(f"subsidies count: {r.scalar_one_or_none()}")
        except Exception as e:
            print(f"Error checking subsidies: {e}")

        # sample rows
        try:
            q = text("SELECT id, station_code, name, address FROM stations LIMIT 5;")
            r = await conn.execute(q)
            rows = r.mappings().all()
            print("\nSample stations:")
            for row in rows:
                print(row)
        except Exception as e:
            print(f"Error fetching sample stations: {e}")

    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
