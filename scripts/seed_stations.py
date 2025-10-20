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
import json
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
    # This function uses the same /ws/chargePoint/curChargePoint endpoint pattern.
    # Some endpoints (like chargePoint/curChargePoint) only accept POST; try GET
    # first and fall back to POST if we receive 405 Method Not Allowed.
    headers = {"Accept": "application/json"}
    if API_KEY and AUTH_TYPE == "header":
        headers["Authorization"] = API_KEY

    # Query params for GET (if using query auth)
    params = None
    if API_KEY and AUTH_TYPE == "query":
        params = {"apiKey": API_KEY, "returnType": "json"}

    url = BASE_URL.rstrip('/')

    # Try GET first
    try:
        resp = await client.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        # If server says GET not allowed, try POST with JSON body
        if e.response.status_code == 405:
            body = {"pageNumber": page, "pageSize": page_size, "searchStatus": False}
            if API_KEY:
                # include API key and returnType in body for Kepco
                if AUTH_TYPE == "query":
                    body["apiKey"] = API_KEY
                else:
                    # header auth: keep header
                    pass
                body["returnType"] = "json"
            try:
                post_resp = await client.post(url, json=body, headers=headers, timeout=60)
                post_resp.raise_for_status()
                return post_resp.json()
            except Exception:
                # re-raise original for upstream handling
                raise
        # re-raise other HTTP errors
        raise
    except Exception:
        # For network errors and others, re-raise to caller
        raise


async def main():
    if not ASYNC_DB:
        print("DATABASE_URL not set")
        return
    if not BASE_URL:
        print("EXTERNAL_STATION_API_BASE_URL not set")
        return

    # Some environments put sslmode=require in the DATABASE_URL (libpq-style).
    # asyncpg does not accept an 'sslmode' keyword; remove it from the URL and
    # pass ssl via connect_args instead.
    connect_args = None
    async_db_url = ASYNC_DB
    try:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

        parsed = urlparse(ASYNC_DB)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        if 'sslmode' in qs:
            qs.pop('sslmode', None)
            new_query = urlencode(qs, doseq=True)
            async_db_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
            connect_args = {'ssl': True}
    except Exception:
        async_db_url = ASYNC_DB

    engine = create_async_engine(async_db_url, echo=False, connect_args=connect_args or None)
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
                # Build at least one charger object from the raw item so upsert
                # will create chargers as well. Detailed connector types may not
                # be available here; leave connector_types empty for now.
                charger_list = []
                if cpId:
                    # Normalize charger type: prefer cpTp (string). If ChargePointType is
                    # a dict, extract cType keys with non-zero values or fallback to a
                    # truncated JSON string to fit DB varchar(50).
                    raw_type = it.get('cpTp')
                    type_str = None
                    if isinstance(raw_type, str):
                        type_str = raw_type
                    else:
                        cpt = it.get('ChargePointType') or it.get('ChargePointType'.lower())
                        if isinstance(cpt, dict):
                            types = [k for k, v in cpt.items() if k.startswith('cType') and v]
                            if types:
                                type_str = ",".join(types)
                            else:
                                # Fallback to short JSON representation
                                try:
                                    j = json.dumps(cpt, ensure_ascii=False)
                                    type_str = j[:50]
                                except Exception:
                                    type_str = None
                        else:
                            # Fallback: stringify whatever is present
                            if raw_type is not None:
                                type_str = str(raw_type)[:50]

                    charger_list.append({
                        "id": cpId,
                        "charger_code": cpId,
                        "type": type_str,
                        "connector_types": [],
                        "max_power_kw": None,
                        "raw": it
                    })

                parsed.append({
                    "id": station_id,
                    "name": name,
                    "address": address,
                    "lat": lat,
                    "lon": lon,
                    "raw": it,
                    "chargers": charger_list,
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
                        # preserve charger list parsed from the raw item
                        "chargers": p.get("chargers", []),
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
