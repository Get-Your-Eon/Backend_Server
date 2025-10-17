from typing import List, Dict, Any, Optional
import math
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Station, Charger


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return int(round(2 * R * math.asin(math.sqrt(a))))


async def get_nearby_stations_db(session: AsyncSession, lat: float, lon: float, radius_m: int, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Simple bounding-box DB query using Station.latitude/longitude properties provided by models' Geometry column.
    Falls back to returning candidates and computing precise distances in-app.
    """
    # Compute rough delta (degrees)
    delta_lat = radius_m / 111000.0
    try:
        delta_lon = radius_m / (111000.0 * max(0.000001, math.cos(math.radians(lat))))
    except Exception:
        delta_lon = radius_m / 111000.0

    minLat = lat - delta_lat
    maxLat = lat + delta_lat
    minLon = lon - delta_lon
    maxLon = lon + delta_lon

    # Query candidate stations using mapped properties (latitude/longitude via geometry)
    q = select(Station).where(
        Station.location.isnot(None)
    ).limit(1000)

    result = await session.execute(q)
    rows = result.scalars().all()

    candidates = []
    for s in rows:
        lat_s = s.latitude
        lon_s = s.longitude
        if lat_s is None or lon_s is None:
            continue
        if not (minLat <= lat_s <= maxLat and minLon <= lon_s <= maxLon):
            continue
        dist = haversine_m(lat, lon, lat_s, lon_s)
        candidates.append({
            "station": s,
            "lat": lat_s,
            "lon": lon_s,
            "distance_m": dist
        })

    # sort and paginate
    candidates.sort(key=lambda x: x["distance_m"])
    paged = candidates[offset: offset + limit]

    out = []
    for c in paged:
        s = c["station"]
        out.append({
            "id": s.station_code or str(s.id),
            "name": s.name,
            "address": s.address,
            "lat": c["lat"],
            "lon": c["lon"],
            "distance_m": c["distance_m"],
            "charger_count": len(s.chargers) if s.chargers is not None else None
        })

    return out


async def upsert_stations_and_chargers(session: AsyncSession, stations: List[Dict[str, Any]]):
    """Upsert stations and associated chargers into DB.
    `stations` is a list of parsed station dicts from external API with keys: id (station_code), name, address, lat, lon, chargers (list)
    """
    for st in stations:
        code = st.get("id")
        name = st.get("name")
        address = st.get("address")
        lat = st.get("lat")
        lon = st.get("lon")

        # find existing
        existing = None
        if code:
            q = select(Station).where(Station.station_code == code)
            res = await session.execute(q)
            existing = res.scalars().first()

        if existing:
            existing.name = name or existing.name
            existing.address = address or existing.address
            if lat is not None and lon is not None:
                existing.location = f'POINT({lon} {lat})'
            station_obj = existing
        else:
            station_obj = Station(
                station_code=code or None,
                name=name or "",
                address=address,
            )
            if lat is not None and lon is not None:
                station_obj.location = f'POINT({lon} {lat})'
            session.add(station_obj)
            await session.flush()

        # chargers: replace (simple strategy)
        # delete existing chargers for station
        await session.execute(delete(Charger).where(Charger.station_id == station_obj.id))
        ch_list = st.get("chargers") or []
        for ch in ch_list:
            charger = Charger(
                station_id=station_obj.id,
                charger_code=ch.get("id") or ch.get("charger_code"),
                charger_type=ch.get("type"),
                connector_type=ch.get("connector_types")[0] if ch.get("connector_types") else None,
                output_kw=ch.get("max_power_kw") or ch.get("output_kw"),
                status_code=None
            )
            session.add(charger)
    await session.commit()
