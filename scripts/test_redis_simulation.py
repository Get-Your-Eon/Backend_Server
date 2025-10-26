#!/usr/bin/env python3
"""
Simulate cache behavior locally and attempt a non-destructive Redis connection test.

- Builds cache keys using application settings precision
- Simulates in-memory cache behavior (no external Redis required)
- Attempts to initialize real Redis connection using app.redis_client.init_redis_pool()
  (this is non-destructive and will not delete any keys)

Usage:
  python3 scripts/test_redis_simulation.py

"""
import asyncio
import time
import json
from pprint import pprint

from app.core.config import settings
from app.redis_client import init_redis_pool, get_redis_client

# Sample coordinates/radii to test
TESTS = [
    (37.4073, 127.0079, 600),
    (37.4073, 127.0079, 1000),
    (37.4030, 127.0070, 2000),
]

# simple in-memory fake redis structure: key -> (value, expire_ts)
fake_redis = {}


def make_cache_key(lat, lon, radius):
    coord_decimals = getattr(settings, "CACHE_COORD_ROUND_DECIMALS", 8)
    lat_round = round(float(lat), coord_decimals)
    lon_round = round(float(lon), coord_decimals)
    return f"stations:lat{lat_round}:lon{lon_round}:r{radius}"


def set_fake(key, value, ex):
    expire_at = time.time() + ex if ex else None
    fake_redis[key] = (value, expire_at)


def get_fake(key):
    rec = fake_redis.get(key)
    if not rec:
        return None
    value, expire_at = rec
    if expire_at and time.time() > expire_at:
        del fake_redis[key]
        return None
    return value


async def try_redis_connect():
    print("\n[Redis real connection test] Attempting to init redis pool (non-destructive)")
    try:
        await init_redis_pool()
        client = await get_redis_client()
        if client:
            print(f"✅ Connected to Redis ({settings.REDIS_HOST}:{settings.REDIS_PORT}) — ping OK")
        else:
            print(f"⚠️ init_redis_pool returned no client (redis_pool is None)")
    except Exception as e:
        print(f"⚠️ Exception while init_redis_pool: {e}")


def simulate_cache_behavior():
    print("\n[Simulation] Application cache settings:")
    print(f"  SEARCH TTL (seconds): {settings.CACHE_EXPIRE_SECONDS}")
    print(f"  DETAIL TTL (seconds): {getattr(settings, 'CACHE_DETAIL_EXPIRE_SECONDS', 'NOT_SET')}")
    print(f"  COORD ROUND DECIMALS: {settings.CACHE_COORD_ROUND_DECIMALS}\n")

    for lat, lon, radius in TESTS:
        key = make_cache_key(lat, lon, radius)
        print(f"Simulating for lat={lat}, lon={lon}, radius={radius} -> key={key}")

        # initial get (should be miss)
        val = get_fake(key)
        print("  initial get:", "HIT" if val else "MISS")

        # simulate DB result (non-empty)
        db_result = [{"station_id": "S1", "lat": str(lat), "lon": str(lon), "distance_m": "10"}]
        # simulate storing search results
        if db_result:
            set_fake(key, {"stations": db_result, "timestamp": time.time()}, settings.CACHE_EXPIRE_SECONDS)
            print(f"  stored non-empty search result into fake redis with TTL={settings.CACHE_EXPIRE_SECONDS}s")
        else:
            print("  would skip caching empty search result (per policy)")

        # immediate read back
        val2 = get_fake(key)
        print("  immediate get after set:", "HIT" if val2 else "MISS")

        # simulate waiting past TTL
        time.sleep(0.1)
        print("  (simulated wait small) still present?", "YES" if get_fake(key) else "NO")

    # station detail caching behavior
    detail_key = "station_detail:TEST_STATION"
    detail_value = {"station_info": {"station_id": "TEST_STATION"}, "chargers": []}
    print(f"\nSimulating station detail cache set with TTL={settings.CACHE_DETAIL_EXPIRE_SECONDS}s -> key={detail_key}")
    set_fake(detail_key, detail_value, getattr(settings, 'CACHE_DETAIL_EXPIRE_SECONDS', 1800))
    print("  immediate get:", "HIT" if get_fake(detail_key) else "MISS")


if __name__ == '__main__':
    print("Starting local Redis simulation + health check")
    simulate_cache_behavior()

    # attempt real redis connect (non-destructive)
    asyncio.run(try_redis_connect())

    print("\nFake redis contents sample:")
    pprint(fake_redis)
    print("\nDone.")
