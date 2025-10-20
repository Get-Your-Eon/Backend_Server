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
# Optional: limit pages processed during seed to avoid long-running or infinite
# runs. Default is 10 pages when the variable is not set. Set SEED_MAX_PAGES=0
# explicitly to disable the limit (not recommended on production datasets).
raw_limit = os.getenv("SEED_MAX_PAGES")
try:
    if raw_limit is None:
        SEED_MAX_PAGES = 10
    else:
        SEED_MAX_PAGES = int(raw_limit)
except Exception:
    SEED_MAX_PAGES = 10


async def fetch_page(client: httpx.AsyncClient, page: int, page_size: int = 100):
    # This function uses the same /ws/chargePoint/curChargePoint endpoint pattern
    cond = {
        "pageNumber": page,
        "pageSize": page_size,
        "searchStatus": False
    }
    if API_KEY and AUTH_TYPE == "query":
        # Kepco expects apiKey as query parameter name and returnType=json
        params = {"apiKey": API_KEY, "returnType": "json"}
    else:
        params = None
    headers = {"Accept": "application/json"}
    if API_KEY and AUTH_TYPE == "header":
        headers["Authorization"] = API_KEY

    # Kepco: use GET/POST to the EVchargeManage endpoint; prefer GET with params for discovery
    resp = await client.get(f"{BASE_URL.rstrip('/')}", params=params, timeout=30)
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
    print(f"Starting seed: BASE_URL={BASE_URL}, SEED_MAX_PAGES={SEED_MAX_PAGES}")
    while True:
            # safety: stop if we've reached configured max pages
            if SEED_MAX_PAGES > 0 and page > SEED_MAX_PAGES:
                print(f"Reached SEED_MAX_PAGES={SEED_MAX_PAGES}, stopping.")
                break
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
            # rate limit modestly (use non-blocking sleep inside async loop)
            await asyncio.sleep(0.2)

    print(f"Seeding finished. Total fetched: {total_fetched}")
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
