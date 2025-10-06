import json
from datetime import datetime
from typing import Optional, Any, List

from fastapi import APIRouter, Depends, HTTPException
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import redis.asyncio as redis
from geoalchemy2.functions import ST_DWithin, ST_SetSRID, ST_Point
from geoalchemy2.shape import to_shape

# 프로젝트 내부 모듈 임포트
from ...models import Station, Charger, get_async_session
from ...schemas import StationPublic, ChargerStatusUpdate, ChargerBase
from ...redis_client import get_redis_client, set_cache, get_cache
from ...mock_api import get_mock_charger_status
from ...config import settings

router = APIRouter()

# ----------------------------------------------------
# V1 API 기본 헬스 체크
# ----------------------------------------------------
@router.get("/", summary="V1 API 기본 테스트", tags=["Test"])
async def v1_root():
    return {"message": "V1 API is running successfully!"}

# ----------------------------------------------------
# A. 충전소 (Stations) 엔드포인트
# ----------------------------------------------------
@router.get(
    "/stations",
    response_model=List[StationPublic],
    summary="충전소 목록 조회 및 검색",
    tags=["Stations"]
)
async def get_stations(
        latitude: float = 37.5665,
        longitude: float = 126.9780,
        radius_km: float = 1.0,
        db: AsyncSession = Depends(get_async_session)
):
    try:
        # 좌표 SRID 맞춤
        search_point = ST_SetSRID(ST_Point(longitude, latitude), 4326)
        distance_meters = radius_km * 1000

        query = (
            select(Station)
            .where(ST_DWithin(Station.location, search_point, distance_meters))
            .order_by(func.ST_Distance(Station.location, search_point))
        )
        result = await db.execute(query)
        stations_db = result.scalars().all()

        # DB 좌표 → lon/lat로 변환
        stations_read = []
        for s in stations_db:
            geom = to_shape(s.location)  # Shapely Point
            station_dict = StationPublic.model_validate(s, from_attributes=True).model_dump()
            station_dict.update({
                "longitude": geom.x,
                "latitude": geom.y
            })
            stations_read.append(station_dict)

        return stations_read

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve stations: {e}"
        )

@router.get(
    "/stations/{station_code}",
    response_model=StationPublic,
    summary="특정 충전소 상세 조회",
    tags=["Stations"]
)
async def get_station_detail(
        station_code: str,
        db: AsyncSession = Depends(get_async_session)
):
    query = select(Station).where(Station.station_code == station_code)
    result = await db.execute(query)
    station_db = result.scalars().first()

    if not station_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station with code {station_code} not found"
        )

    geom = to_shape(station_db.location)
    station_dict = StationPublic.model_validate(station_db, from_attributes=True).model_dump()
    station_dict.update({
        "longitude": geom.x,
        "latitude": geom.y
    })
    return station_dict

# ----------------------------------------------------
# B. 충전기 (Chargers) 엔드포인트
# ----------------------------------------------------
def get_charger_cache_key(station_code: str, charger_code: str) -> str:
    return f"charger_status:{station_code}:{charger_code}"

@router.patch(
    "/chargers/{station_code}/{charger_code}/status",
    response_model=ChargerBase,
    summary="충전기 상태 업데이트 (DB 및 Cache)",
    tags=["Chargers"]
)
async def update_charger_status(
        station_code: str,
        charger_code: str,
        update_data: ChargerStatusUpdate,
        db: AsyncSession = Depends(get_async_session),
        redis_client: Optional[redis.Redis] = Depends(get_redis_client)
):
    station_id_subquery = select(Station.id).where(Station.station_code == station_code).scalar_subquery()
    query = select(Charger).where(
        Charger.charger_code == charger_code,
        Charger.station_id == station_id_subquery
    )
    result = await db.execute(query)
    charger_db = result.scalars().first()

    if not charger_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Charger {charger_code} at station {station_code} not found"
        )

    charger_db.status_code = update_data.new_status_code
    charger_db.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(charger_db)

    if redis_client:
        cache_key = get_charger_cache_key(station_code, charger_code)
        cache_value = {
            "status_code": charger_db.status_code,
            "updated_at": str(charger_db.updated_at),
            "charger_type": charger_db.charger_type,
            "output_kw": float(charger_db.output_kw) if charger_db.output_kw else None
        }
        await set_cache(cache_key, cache_value, expire=settings.CACHE_EXPIRE_SECONDS)

    return ChargerBase.model_validate(charger_db, from_attributes=True)

@router.get(
    "/chargers/status/{station_code}/{charger_code}",
    response_model=dict,
    summary="충전기 실시간 상태 조회 (Cache 우선)",
    tags=["Chargers"]
)
async def get_charger_status(
        station_code: str,
        charger_code: str,
        db: AsyncSession = Depends(get_async_session),
        redis_client: Optional[redis.Redis] = Depends(get_redis_client)
):
    cache_key = get_charger_cache_key(station_code, charger_code)
    cached_data = await get_cache(cache_key)
    if cached_data:
        return {"source": "cache", "status_data": cached_data}

    station_id_subquery = select(Station.id).where(Station.station_code == station_code).scalar_subquery()
    query = select(Charger).where(
        Charger.charger_code == charger_code,
        Charger.station_id == station_id_subquery
    )
    result = await db.execute(query)
    charger_db = result.scalars().first()

    if charger_db:
        realtime_status_code = await get_mock_charger_status(station_code, charger_code)
        if realtime_status_code is not None and realtime_status_code != charger_db.status_code:
            charger_db.status_code = realtime_status_code
            charger_db.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(charger_db)

        cache_value = {
            "status_code": charger_db.status_code,
            "updated_at": str(charger_db.updated_at),
            "charger_type": charger_db.charger_type,
            "output_kw": float(charger_db.output_kw) if charger_db.output_kw else None
        }
        await set_cache(cache_key, cache_value, expire=settings.CACHE_EXPIRE_SECONDS)

        return {"source": "database", "status_data": cache_value}

    mock_status = await get_mock_charger_status(station_code, charger_code)
    if mock_status is not None:
        return {"source": "mock_api", "status_code": mock_status, "note": "Data not found in DB or Cache. Status is simulated."}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Status for Charger {charger_code} at station {station_code} not found."
    )
