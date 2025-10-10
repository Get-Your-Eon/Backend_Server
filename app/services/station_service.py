import json
from typing import List, Dict

# SQLAlchemy 비동기 세션 임포트
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text # 원시 SQL 쿼리를 실행하기 위해 text() 함수를 임포트

# ⚠️ GeoAlchemy2 ST_Point 함수 임포트 (Point 객체 생성을 명확하게 하기 위함)
from geoalchemy2.functions import ST_Point

# Redis 클라이언트 및 캐시 관리 함수 임포트
from app.redis_client import get_cache, set_cache, get_redis_client # type: ignore

# DB 모델 및 Mock API 임포트
from app.models import Station, Charger # type: ignore
from app.mock_api import get_mock_stations  # type: ignore

# 캐시 만료 시간 설정
CACHE_EXPIRE_SECONDS = 3600  # 1시간 캐시 유지

# ----------------------------------------------------
# 충전소 조회 서비스
# ----------------------------------------------------
async def get_stations(
        db: AsyncSession,
        lat: float,
        lng: float,
        radius_m: float = 5000,
        redis_client=None
) -> List[Dict]:
    """
    주어진 좌표(lat, lng) 반경 radius_m 내의 충전소 목록을 조회합니다.
    캐시 Redis 우선 조회 후 DB 또는 Mock API 사용.
    """
    cache_key = f"station:{lat}:{lng}:{radius_m}"

    cached = await get_cache(cache_key, client=redis_client)
    if cached:
        print(f"INFO: Stations data retrieved from cache for key: {cache_key}")
        return cached

    # 1. DB 쿼리 실행
    query = text(
        "SELECT * FROM stations "
        "WHERE ST_DWithin(location, ST_MakePoint(:lng, :lat)::geography, :radius_m)"
    )

    result = await db.execute(
        query,
        {"lat": lat, "lng": lng, "radius_m": radius_m}
    )

    # DB 결과가 dict 리스트로 반환되므로, station_code를 추출할 수 없습니다.
    # 따라서, ORM 객체로 변환하여 사용하거나, text 대신 select(Station) 쿼리를 사용해야 합니다.
    # 여기서는 text 쿼리 결과를 유지하고, Mock 삽입 로직을 개선하겠습니다.
    stations = [dict(r) for r in result.fetchall()]
    stations_to_cache = stations # DB에서 조회된 결과는 바로 캐시에 저장할 수 있도록 준비

    if not stations:
        # DB에 데이터 없으면 Mock API 사용
        print(f"INFO: DB에 충전소 정보 없음. Mock API({lat}, {lng})를 사용하여 데이터 초기 로딩 시작.")

        mock_stations = await get_mock_stations(lat, lng, radius_km=radius_m / 1000)

        # ⚠️ 수정된 부분: 현재 DB에 존재하는 station_code 목록을 조회합니다.
        # 비어있는 DB라고 가정했지만, 롤백 등으로 인해 일부 데이터만 남을 수 있습니다.
        existing_codes_result = await db.execute(text("SELECT station_code FROM stations"))
        existing_codes = {row[0] for row in existing_codes_result.fetchall()}

        # Mock API 데이터를 DB에 삽입
        new_stations = []
        for s in mock_stations:
            # ⚠️ 중복 방지 로직 추가: station_code가 DB에 없으면 삽입합니다.
            if s["station_code"] in existing_codes:
                print(f"WARN: Charger {s['station_code']} already exists. Skipping insertion.")
                continue

            # ⚠️ 핵심 수정: WKT 문자열 대신 ST_Point 함수를 사용하여 Point 객체를 생성합니다.
            # PostGIS는 경도, 위도 순서를 따릅니다. (longitude, latitude)
            point = ST_Point(s["longitude"], s["latitude"], srid=4326)

            new_station = Station(
                station_code=s["station_code"],
                name=s["name"],
                address=s.get("address"),
                provider=s.get("provider"),
                location=point # PostGIS Point 객체 할당
            )
            db.add(new_station)
            new_stations.append(new_station)

        if new_stations: # 삽입할 데이터가 있는 경우에만 커밋합니다.
            await db.commit() # 변경사항 커밋

            # ⚠️ DB에 저장된 객체의 ID를 포함하여 캐시/응답 데이터를 재구성하기 위해 refresh
            try:
                # 리스트 전체 refresh (Mock 데이터가 많지 않다면 안전함)
                for ns in new_stations:
                    await db.refresh(ns)
            except Exception as refresh_e:
                # refresh 실패는 500 에러를 유발할 수 있으므로, 로그를 남기고 다음 단계로 진행합니다.
                print(f"WARN: DB Refresh failed after insertion: {refresh_e}. Proceeding.")

            # DB에 저장된 Mock 데이터를 반환 리스트로 사용 (Dict 형태로 재구성)
            stations_to_cache = [
                {
                    "id": ns.id,
                    "station_code": ns.station_code,
                    "name": ns.name,
                    "address": ns.address,
                    "provider": ns.provider,
                    # @property를 사용하여 latitude/longitude를 가져옵니다.
                    "latitude": ns.latitude,
                    "longitude": ns.longitude,
                    "chargers": []
                }
                # ns.id가 None인 경우 (refresh 실패)를 방지하기 위해 필터링하거나 처리 로직 추가 필요
                for ns in new_stations if ns.id is not None
            ]

    # 2. 조회 결과를 캐시에 저장
    await set_cache(cache_key, stations_to_cache, expire=CACHE_EXPIRE_SECONDS, client=redis_client)
    return stations_to_cache

# ----------------------------------------------------
# 충전기 조회 서비스
# ----------------------------------------------------
async def get_chargers(
        db: AsyncSession,
        station_id: int,
        redis_client=None
) -> List[Dict]:
    """
    특정 충전소(station_id)에 속한 모든 충전기를 조회합니다.
    캐시 Redis 우선 조회 후 DB 조회.
    """
    cache_key = f"charger:{station_id}"

    cached = await get_cache(cache_key, client=redis_client)
    if cached:
        print(f"INFO: Chargers data retrieved from cache for key: {cache_key}")
        return cached

    query = text("SELECT * FROM chargers WHERE station_id=:station_id")
    result = await db.execute(
        query,
        {"station_id": station_id}
    )
    chargers = [dict(r) for r in result.fetchall()]

    await set_cache(cache_key, chargers, expire=CACHE_EXPIRE_SECONDS, client=redis_client)
    return chargers
