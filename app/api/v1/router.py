import json
from datetime import datetime
from typing import Optional, Any, List

# 🚨 status 모듈을 starlette에서 명시적으로 임포트하여 참조 오류를 해결합니다.
from fastapi import APIRouter, Depends, HTTPException
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import redis.asyncio as redis
from geoalchemy2.functions import ST_DWithin, ST_Point

# 프로젝트 내부 모듈 임포트
from ...models import Station, Charger, get_async_session
from ...schemas import StationPublic, ChargerStatusUpdate, ChargerBase
from ...redis_client import get_redis_client, set_cache, get_cache
from ...mock_api import get_mock_charger_status
from ...config import settings

# V1 API의 메인 라우터 인스턴스를 생성합니다.
router = APIRouter()

# ----------------------------------------------------
# [수정] 사용자 기능 제거: user_router 임포트 및 포함 코드를 제거합니다.
# ----------------------------------------------------

# ----------------------------------------------------
# A. 충전소 (Stations) 엔드포인트
# ----------------------------------------------------

# [추가] 헬스 체크 또는 기본 테스트 엔드포인트
@router.get(
    "/",
    summary="V1 API 기본 테스트",
    tags=["Test"]
)
async def v1_root():
    """V1 API 라우터가 정상적으로 로드되었는지 확인합니다."""
    return {"message": "V1 API is running successfully!"}

# 충전소 목록 조회 및 검색 (GET /stations)
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
    """
    주어진 위치(위도, 경도)를 기준으로 반경(km) 내의 충전소 목록을 조회합니다.
    """
    try:
        # PostGIS를 이용한 공간 검색 쿼리
        search_point = ST_Point(longitude, latitude, srid=4326)
        distance_meters = radius_km * 1000

        query = (
            select(Station)
            .where(
                ST_DWithin(Station.location, search_point, distance_meters)
            )
            .order_by(
                func.ST_Distance(Station.location, search_point)
            )
        )

        result = await db.execute(query)
        stations_db = result.scalars().all()

        # StationPublic 스키마에 맞게 응답 데이터 구성
        stations_read = [StationPublic.model_validate(s, from_attributes=True) for s in stations_db]

        return stations_read

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve stations: {e}"
        )

# 충전소 상세 조회 (GET /stations/{code})
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
    """
    특정 충전소 코드(station_code)를 사용하여 상세 정보를 조회합니다.
    """
    query = (
        select(Station)
        .where(Station.station_code == station_code)
    )

    result = await db.execute(query)
    station_db = result.scalars().first()

    if not station_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station with code {station_code} not found"
        )

    return StationPublic.model_validate(station_db, from_attributes=True)


# ----------------------------------------------------
# B. 충전기 (Chargers) 엔드포인트
# ----------------------------------------------------

# Redis 캐시 키 생성 함수 (충전기 엔드포인트 로직에 포함)
def get_charger_cache_key(station_code: str, charger_code: str) -> str:
    """Redis 키를 생성합니다: 'charger_status:ST0001:1'"""
    return f"charger_status:{station_code}:{charger_code}"


# 1. 충전기 상태 업데이트 (PATCH /chargers/{station_code}/{charger_code}/status)
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
    """
    특정 충전기의 상태 코드를 업데이트하고, 해당 변경 사항을 Redis 캐시에 반영합니다.
    """

    # 1. DB에서 충전기 조회 (Charger 테이블과 Station 테이블을 조인하여 ID 검색)
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

    # 2. 상태 업데이트
    charger_db.status_code = update_data.new_status_code
    charger_db.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(charger_db)

    # 3. Redis 캐시 업데이트
    if redis_client:
        cache_key = get_charger_cache_key(station_code, charger_code)

        cache_value = {
            "status_code": charger_db.status_code,
            "updated_at": str(charger_db.updated_at),
            "charger_type": charger_db.charger_type,
            # Decimal 타입이 json.dumps에 의해 직렬화될 수 있도록 float으로 변환
            "output_kw": float(charger_db.output_kw) if charger_db.output_kw else None
        }

        # settings.CACHE_EXPIRE_SECONDS는 app/config.py에서 정의됨
        await set_cache(cache_key, cache_value, expire=settings.CACHE_EXPIRE_SECONDS)

    return ChargerBase.model_validate(charger_db, from_attributes=True)


# 2. 충전기 상태 조회 (GET /chargers/status/{station_code}/{charger_code})
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
    """
    Redis 캐시, DB, Mock API 순서로 충전기 상태를 조회합니다.
    """
    cache_key = get_charger_cache_key(station_code, charger_code)

    # 1. Redis 캐시 조회
    cached_data = await get_cache(cache_key)
    if cached_data:
        return {"source": "cache", "status_data": cached_data}

    # 2. DB 조회
    station_id_subquery = select(Station.id).where(Station.station_code == station_code).scalar_subquery()

    query = select(Charger).where(
        Charger.charger_code == charger_code,
        Charger.station_id == station_id_subquery
    )
    result = await db.execute(query)
    charger_db = result.scalars().first()

    if charger_db:
        # DB에서 조회한 데이터를 Mock API를 통해 실시간 상태로 업데이트 (실제 시스템 모방)
        # Mock API의 반환값은 정수형 상태 코드입니다.
        realtime_status_code = await get_mock_charger_status(station_code, charger_code)

        # Mock API 상태가 다를 경우 DB 업데이트
        if realtime_status_code is not None and realtime_status_code != charger_db.status_code:
            charger_db.status_code = realtime_status_code
            charger_db.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(charger_db)

        # 캐시 생성에 사용할 값
        cache_value = {
            "status_code": charger_db.status_code,
            "updated_at": str(charger_db.updated_at),
            "charger_type": charger_db.charger_type,
            "output_kw": float(charger_db.output_kw) if charger_db.output_kw else None
        }
        await set_cache(cache_key, cache_value, expire=settings.CACHE_EXPIRE_SECONDS)

        return {"source": "database", "status_data": cache_value}

    # 3. Mock API Fallback (DB에도 없을 경우)
    mock_status = await get_mock_charger_status(station_code, charger_code)
    if mock_status is not None:
        # Mock API 결과는 캐시하지 않고 바로 반환
        return {"source": "mock_api", "status_code": mock_status, "note": "Data not found in DB or Cache. Status is simulated."}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Status for Charger {charger_code} at station {station_code} not found."
    )