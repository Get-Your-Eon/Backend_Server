import json
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import redis.asyncio as redis
from geoalchemy2.functions import ST_DWithin, ST_SetSRID, ST_Point
from geoalchemy2.shape import to_shape
import geoalchemy2.types  # PostGIS 타입 임포트 (마이그레이션 오류 방지용)

# 프로젝트 내부 모듈 임포트
from ...models import Station, Charger
from ...database import get_async_session
from ...schemas import StationPublic, ChargerBase, ChargerStatusUpdate
from ...redis_client import get_redis_client, set_cache, get_cache
from ...mock_api import get_mock_charger_status
from ...config import settings
from app.services.station_service import get_stations as service_get_stations

# Subsidy router
from app.api.v1.subsidy_router import router as subsidy_v1_router

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
        # 1. DB 세션 종속성을 라우터 함수 매개변수에 추가합니다. (이 부분이 누락되어 있었습니다.)
        db: AsyncSession = Depends(get_async_session),
        latitude: float = 37.5665,
        longitude: float = 126.9780,
        radius_km: float = 1.0,
        redis_client: Optional[redis.Redis] = Depends(get_redis_client)
):
    try:
        # 2. service_get_stations 호출 시, db를 첫 번째 인수로 정확히 전달합니다.
        # 명확성을 위해 키워드 인자를 사용하여 순서 오류를 방지합니다.
        stations = await service_get_stations(
            db=db,
            lat=latitude,
            lng=longitude,
            radius_m=radius_km*1000,
            redis_client=redis_client
        )
        return stations
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


# ----------------------------------------------------
# C. 보조금 (Subsidies) 엔드포인트 통합
# ----------------------------------------------------
router.include_router(subsidy_v1_router)
