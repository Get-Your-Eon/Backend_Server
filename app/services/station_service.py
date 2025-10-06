from app.database import get_async_session
from app.redis_client import redis
from app.models import Station, Charger, ChargerStatus
from app.mock_api import get_mock_stations
import json

async def get_stations(lat: float, lng: float):
    cache_key = f"station:{lat}:{lng}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    async with get_async_session() as session:
        result = await session.execute(
            "SELECT * FROM stations WHERE ST_DWithin(location, ST_MakePoint(:lng, :lat)::geography, 5000)",
            {"lat": lat, "lng": lng}
        )
        stations = [dict(r) for r in result.fetchall()]

    if not stations:
        stations = await get_mock_stations(lat, lng, radius_km=5)
        async with get_async_session() as session:
            for s in stations:
                session.add(Station(
                    station_code=s["station_code"],
                    name=s["name"],
                    address=s["address"],
                    provider=s["provider"],
                    location=f'POINT({s["longitude"]} {s["latitude"]})'
                ))
            await session.commit()

    await redis.set(cache_key, json.dumps(stations), ex=3600)
    return stations

async def get_chargers(station_id: int):
    cache_key = f"charger:{station_id}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    async with get_async_session() as session:
        result = await session.execute(
            "SELECT * FROM chargers WHERE station_id=:station_id",
            {"station_id": station_id}
        )
        chargers = [dict(r) for r in result.fetchall()]

    return chargers
