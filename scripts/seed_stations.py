"""Seed stations and chargers from external API into DB.

Configuration via environment variables (already used by app):
- EXTERNAL_STATION_API_BASE_URL
- EXTERNAL_STATION_API_KEY (optional)
- EXTERNAL_STATION_API_AUTH_TYPE (header|query)

Run:
  export DATABASE_URL=postgresql+asyncpg://...\
  export EXTERNAL_STATION_API_BASE_URL=https://chargeinfo.ksga.org\
  export EXTERNAL_STATION_API_KEY=your_key_here
  python scripts/seed_stations.py
"""
import os
import asyncio
import time
import httpx
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.repository.station import upsert_stations_and_chargers


ASYNC_DB = os.getenv("DATABASE_URL")
BASE_URL = os.getenv("EXTERNAL_STATION_API_BASE_URL")
API_KEY = os.getenv("EXTERNAL_STATION_API_KEY")
AUTH_TYPE = os.getenv("EXTERNAL_STATION_API_AUTH_TYPE", "header")


async def fetch_page(client: httpx.AsyncClient, page: int, page_size: int = 100):
    # This function uses the same /ws/chargePoint/curChargePoint endpoint pattern
    cond = {
        "pageNumber": page,
        "pageSize": page_size,
        "searchStatus": False
    }
    if API_KEY and AUTH_TYPE == "query":
        params = {"serviceKey": API_KEY}
    else:
        params = None
    headers = {"Accept": "application/json"}
    if API_KEY and AUTH_TYPE == "header":
        headers["Authorization"] = API_KEY

    resp = await client.post(f"{BASE_URL.rstrip('/')}/ws/chargePoint/curChargePoint", json=cond, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


async def main():
    if not ASYNC_DB:
        print("DATABASE_URL not set")
        return
    if not BASE_URL:
        print("EXTERNAL_STATION_API_BASE_URL not set")
        return

    engine = create_async_engine(ASYNC_DB, echo=False)
    AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with httpx.AsyncClient() as client:
        page = 1
        page_size = 100
        total_fetched = 0
        while True:
            try:
                data = await fetch_page(client, page, page_size)
            except Exception as e:
                print(f"fetch page {page} failed: {e}")
                await asyncio.sleep(5)
                continue

            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("result") or data.get("data") or []

            if not items:
                print("No more items, finishing")
                break

            # parse items into our station dict format expected by upsert
            parsed = []
            for it in items:
                bid = it.get('bid') or ''
                cpId = it.get('cpId') or it.get('cpid') or ''
                station_id = f"{bid}_{cpId}"
                lat = it.get('lat') or it.get('latitude') or it.get('y')
                lon = it.get('lon') or it.get('longitude') or it.get('x')
                name = it.get('cpName') or it.get('cp_name') or ''
                address = it.get('addr') or it.get('roadName') or ''
                # charger list will be fetched later by separate call in upsert or here
                parsed.append({
                    "id": station_id,
                    "name": name,
                    "address": address,
                    "lat": lat,
                    "lon": lon,
                    "raw": it
                })

            async with AsyncSessionLocal() as session:
                # adapt parsed to the upsert helper shape
                to_upsert = []
                for p in parsed:
                    st = {
                        "id": p["id"],
                        "name": p["name"],
                        "address": p["address"],
                        "lat": p["lat"],
                        "lon": p["lon"],
                        "chargers": [],
                    }
                    to_upsert.append(st)
                try:
                    await upsert_stations_and_chargers(session, to_upsert)
                except Exception as e:
                    print(f"upsert failed on page {page}: {e}")

            total_fetched += len(parsed)
            print(f"Fetched page {page}, items: {len(parsed)}, total: {total_fetched}")
            page += 1
            # rate limit modestly
            time.sleep(0.2)

    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
