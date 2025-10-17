from typing import List, Dict, Any, Optional
from sqlalchemy import text, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Station, Charger


async def get_nearby_stations_db(session: AsyncSession, lat: float, lon: float, radius_m: int, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Uses PostGIS ST_DWithin and ST_Distance to return nearby stations with distance_m.
    Requires PostGIS extension and stations.location geometry column (SRID=4326).
    """
    sql = text(
        """
        SELECT
          COALESCE(station_code, id::text) AS id,
          name,
          address,
          ST_Y(location::geometry) AS lat,
          ST_X(location::geometry) AS lon,
          ST_Distance(location::geography, ST_SetSRID(ST_MakePoint(:lon, :lat),4326)::geography) AS distance_m,
          (SELECT COUNT(1) FROM chargers c WHERE c.station_id = stations.id) AS charger_count
        FROM stations
        WHERE location IS NOT NULL
          AND ST_DWithin(location::geography, ST_SetSRID(ST_MakePoint(:lon, :lat),4326)::geography, :radius)
        ORDER BY distance_m
        LIMIT :limit OFFSET :offset
        """
    )

    result = await session.execute(sql, {"lat": lat, "lon": lon, "radius": radius_m, "limit": limit, "offset": offset})
    rows = result.mappings().all()
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "name": r["name"],
            "address": r["address"],
            "lat": float(r["lat"]) if r["lat"] is not None else None,
            "lon": float(r["lon"]) if r["lon"] is not None else None,
            "distance_m": int(round(float(r["distance_m"]))) if r["distance_m"] is not None else None,
            "charger_count": int(r["charger_count"]) if r["charger_count"] is not None else None,
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
