import contextlib
import time
from datetime import datetime, timezone, timedelta
import os

from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, Response, Header, Body, Query, Path
from typing import Optional
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from redis.asyncio import Redis
import httpx
import math
import json

# 프로젝트 내부 모듈 임포트
from app.core.config import settings
from app.db.database import get_async_session
from app.redis_client import (
    init_redis_pool,
    close_redis_pool,
    get_redis_client,
    set_cache,
    get_cache
)
from app.api.v1.api import api_router
from app.api.deps import frontend_api_key_required

# --- 환경 변수로 관리자 모드 판단 ---
IS_ADMIN = os.getenv("ADMIN_MODE", "false").lower() == "true"

# --- Lifespan Context Manager 정의 ---
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application startup: Initializing resources...")
    await init_redis_pool()
    # [TODO] DB 마이그레이션 확인 및 초기 데이터 로드
    yield
    print("Application shutdown: Cleaning up resources...")
    await close_redis_pool()

# --- HTTP Basic 인증 (관리자 전용) ---
security = HTTPBasic()
raw_admins = os.getenv("ADMIN_CREDENTIALS", "")
ADMIN_ACCOUNTS = dict([cred.split(":") for cred in raw_admins.split(",") if cred])

def admin_required(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username not in ADMIN_ACCOUNTS or ADMIN_ACCOUNTS[credentials.username] != credentials.password:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


# frontend API key dependency moved to `app.api.deps` to avoid circular imports


def ensure_read_only_sql(sql: str):
    """Basic guard to ensure the provided SQL starts with SELECT to avoid write queries.

    This is a defensive, best-effort check and should be combined with parameterized queries and DB user permissions.
    """
    if not sql.strip().lower().startswith("select"):
        raise HTTPException(status_code=400, detail="Only read-only SELECT queries are allowed")

# --- FastAPI Application 생성 ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    description="Codyssey EV Charging Station API",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json" if IS_ADMIN else None
)

# --- CORS: restrict origins to allowed list from env ---
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    allowed_origins = []

if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# --- 관리자용 docs & redoc 엔드포인트 ---
if IS_ADMIN:
    @app.get("/docs", include_in_schema=False)
    async def get_docs(credentials: HTTPBasicCredentials = Depends(admin_required)):
        return get_swagger_ui_html(openapi_url=app.openapi_url, title=f"{settings.PROJECT_NAME} - Swagger UI")

    @app.get("/redoc", include_in_schema=False)
    async def get_redoc(credentials: HTTPBasicCredentials = Depends(admin_required)):
        return get_redoc_html(openapi_url=app.openapi_url, title=f"{settings.PROJECT_NAME} - ReDoc")

# --- 기본 헬스 체크 엔드포인트 ---
@app.get("/", tags=["Infrastructure"])
def read_root():
    return {
        "message": "Server is running successfully!",
        "project": settings.PROJECT_NAME,
        "api_version": settings.API_VERSION
    }


@app.head("/", include_in_schema=False)
def head_root():
    """Explicit HEAD handler to make uptime probes (HEAD) return 200 without body."""
    return Response(status_code=200)


@app.get("/health", tags=["Infrastructure"], summary="Health check (DB & Redis)")
@app.head("/health")    
async def health_check(db: AsyncSession = Depends(get_async_session), redis_client: Redis = Depends(get_redis_client)):
    """Simple health check endpoint. Returns 200 if at least one of DB/Redis responds, 503 if both fail.

    Response body example:
    {
      "status": "ok",
      "db": true,
      "redis": true
    }
    """
    db_ok = False
    redis_ok = False

    # DB check
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    # Redis check
    try:
        if redis_client:
            await redis_client.ping()
            redis_ok = True
    except Exception:
        redis_ok = False

    if db_ok or redis_ok:
        status_str = "ok"
        code = 200
    else:
        status_str = "down"
        code = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(status_code=code, content={"status": status_str, "db": db_ok, "redis": redis_ok})


@app.get("/subsidy", tags=["Subsidy"], summary="Lookup subsidies by manufacturer and model_group")
async def subsidy_lookup(manufacturer: str, model_group: str, db: AsyncSession = Depends(get_async_session), _ok: bool = Depends(frontend_api_key_required)):
    """Return subsidy rows for given manufacturer and model_group.

    Response format (list of objects):
    [
      {
        "model_name": str,
        "subsidy_national": int,
        "subsidy_local": int,
        "subsidy_total": int
      },
      ...
    ]
    """
    try:
        query_sql = (
            "SELECT model_name, subsidy_national_10k_won, subsidy_local_10k_won, subsidy_total_10k_won "
            "FROM subsidies "
            "WHERE manufacturer = :manufacturer AND model_group = :model_group "
            "ORDER BY model_name LIMIT 100"
        )
        ensure_read_only_sql(query_sql)
        result = await db.execute(text(query_sql), {"manufacturer": manufacturer, "model_group": model_group})
        rows = result.fetchall()

        mapped = []
        for r in rows:
            m = r._mapping
            # convert to ints if not None
            nat = m.get("subsidy_national_10k_won")
            loc = m.get("subsidy_local_10k_won")
            tot = m.get("subsidy_total_10k_won")
            mapped.append({
                "model_name": m.get("model_name"),
                "subsidy_national": int(nat) if nat is not None else None,
                "subsidy_local": int(loc) if loc is not None else None,
                "subsidy_total": int(tot) if tot is not None else None,
            })

        return JSONResponse(status_code=200, content=mapped)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/subsidy/by", tags=["Subsidy"], summary="Lookup subsidies (camelCase) by manufacturer and modelGroup")
async def subsidy_lookup_camel(manufacturer: str, modelGroup: str, db: AsyncSession = Depends(get_async_session), _ok: bool = Depends(frontend_api_key_required)):
    """Compatibility wrapper: accept camelCase `modelGroup` from frontend and return subsidy rows.

    Header: x-api-key: <key>
    Query params: manufacturer, modelGroup
    """
    # reuse same logic as /subsidy but accept modelGroup camelCase
    model_group = modelGroup
    try:
        query_sql = (
            "SELECT model_name, subsidy_national_10k_won, subsidy_local_10k_won, subsidy_total_10k_won "
            "FROM subsidies "
            "WHERE manufacturer = :manufacturer AND model_group = :model_group "
            "ORDER BY model_name LIMIT 100"
        )
        ensure_read_only_sql(query_sql)
        result = await db.execute(text(query_sql), {"manufacturer": manufacturer, "model_group": model_group})
        rows = result.fetchall()

        mapped = []
        for r in rows:
            m = r._mapping
            nat = m.get("subsidy_national_10k_won")
            loc = m.get("subsidy_local_10k_won")
            tot = m.get("subsidy_total_10k_won")
            mapped.append({
                "model_name": m.get("model_name"),
                "subsidy_national": int(nat) if nat is not None else None,
                "subsidy_local": int(loc) if loc is not None else None,
                "subsidy_total": int(tot) if tot is not None else None,
            })

        return JSONResponse(status_code=200, content=mapped)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 충전소/충전기 검색 엔드포인트 (보조금 기능과 완전 독립) ---
@app.get("/api/v1/stations-test-new", tags=["Station"], summary="NEW CODE TEST - EV charging stations")
async def search_ev_stations_new_test(
    lat: float = Query(..., description="위도", ge=-90, le=90),
    lon: float = Query(..., description="경도", ge=-180, le=180),
    radius: int = Query(..., description="검색 반경(미터)", ge=100, le=10000),
    page: int = Query(1, description="페이지 번호", ge=1),
    limit: int = Query(20, description="페이지당 결과 수", ge=1, le=100),
    api_key: str = Depends(frontend_api_key_required),
    db: AsyncSession = Depends(get_async_session),
    redis_client: Redis = Depends(get_redis_client)
):
    """🚨 NEW CODE TEST ENDPOINT"""
    print(f"🔥🔥🔥 TEST ENDPOINT - NEW CODE CONFIRMED RUNNING 🔥🔥🔥")
    return {
        "message": "NEW CODE IS RUNNING!",
    "timestamp": datetime.now(timezone.utc).isoformat(),
        "received_params": {"lat": lat, "lon": lon, "radius": radius}
    }

@app.get("/api/v1/stations", tags=["Station"], summary="✅ 요구사항 완전 준수 - 충전소 검색")
async def search_ev_stations_requirement_compliant(
    lat: str = Query(..., description="사용자 위도 (string 타입)", regex=r"^-?\d+\.?\d*$"),
    lon: str = Query(..., description="사용자 경도 (string 타입)", regex=r"^-?\d+\.?\d*$"),
    radius: int = Query(..., description="반경(m) - 500/1000/3000/5000/10000 기준", ge=100, le=10000),
    api_key: str = Depends(frontend_api_key_required),
    db: AsyncSession = Depends(get_async_session),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    ✅ 백엔드 요구사항 완전 준수 구현
    
    1. 사용자 위도/경도(string) → 시/군/구/동 매핑 → addr 생성
    2. Cache 조회 → DB 조회 → API 호출 순서
    3. 반경 기준값(500/1000/3000/5000/10000) 처리
    4. 정적/동적 데이터 분리 저장
    5. 응답: 충전소ID, 충전기주소(addr), 충전소명칭, 위도, 경도 (모두 string)
    """
    print(f"✅ 요구사항 준수 충전소 검색 시작")
    print(f"✅ 입력: lat={lat}, lon={lon}, radius={radius}")
    
    try:
        # === 1단계: 좌표 → 주소 변환 ===
        lat_float = float(lat)
        lon_float = float(lon)
        
        # Nominatim을 통한 역지오코딩
        async with httpx.AsyncClient() as client:
            nominatim_response = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": lat_float,
                    "lon": lon_float,
                    "format": "json",
                    "accept-language": "ko",
                    "addressdetails": 1
                },
                headers={"User-Agent": "Codyssey-EV-App/1.0"},
                timeout=10.0
            )
            
            if nominatim_response.status_code == 200:
                nominatim_data = nominatim_response.json()
                address_components = nominatim_data.get("address", {})
                
                # 시/군/구/동 추출
                city = address_components.get("city") or address_components.get("town") or ""
                district = address_components.get("borough") or address_components.get("suburb") or ""
                addr = f"{city} {district}".strip()
                
                if not addr:
                    addr = "서울특별시"  # 기본값
            else:
                addr = "서울특별시"  # 기본값
        
        print(f"✅ 매핑된 주소: {addr}")
        
        # === 2단계: 반경 기준값 정규화 ===
        # Use "이하" (less than or equal) mapping: 500이하→500, 1000이하→1000, 2000이하→2000, etc.
        # buckets: 500, 1000, 2000, 3000, 5000, 10000 (meters)
        # NOTE: keep this list small and canonical to reduce cache fragmentation.
        radius_standards = [500, 1000, 2000, 3000, 5000, 10000]
        
        # Normalize the requested radius to an integer and find the smallest
        # canonical bucket that is >= the requested radius. This avoids
        # surprising mappings caused by float/string inputs.
        try:
            requested_radius = int(round(float(radius)))
        except Exception:
            requested_radius = radius

        actual_radius = next((r for r in radius_standards if requested_radius <= r), radius_standards[-1])
        print(f"✅ 반경 정규화: requested={requested_radius} -> normalized={actual_radius} (buckets={radius_standards})")
        
        # === 3단계: Cache 조회 ===
        # Use rounded coordinates in the cache key to avoid cache collisions caused
        # by tiny floating differences. Use a configurable decimal precision so we
        # can keep cache keys tightly scoped (e.g. 8 decimals -> ~0.001m precision).
        coord_decimals = getattr(settings, "CACHE_COORD_ROUND_DECIMALS", 8)
        lat_round = round(lat_float, coord_decimals)
        lon_round = round(lon_float, coord_decimals)
        # Use coordinate-first key (avoid addr text differences)
        cache_key = f"stations:lat{lat_round}:lon{lon_round}:r{actual_radius}"

        try:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                print(f"✅ Cache Hit: {cache_key}")
                cached_result = json.loads(cached_data)
                
                # 거리 필터링 후 반환
                filtered_stations = []
                for station in cached_result.get("stations", []):
                    dist = calculate_distance_haversine(
                        lat_float, lon_float,
                        float(station["lat"]), float(station["lon"])
                    )
                    if dist <= radius:
                        station["distance_m"] = str(int(dist))
                        filtered_stations.append(station)
                
                filtered_stations.sort(key=lambda x: int(x["distance_m"]))
                
                return {
                    "source": "cache",
                    "addr": addr,
                    "radius_normalized": actual_radius,
                    "stations": filtered_stations
                }
        except Exception as cache_error:
            print(f"⚠️ Cache 오류: {cache_error}")
        
    # === 4단계: DB 조회 (정적 데이터) ===
        print(f"✅ DB 조회 시작...")
        try:
            # 정적 데이터 조회 (충전기 상태코드 제외)
            # NOTE: some deployments may not have KEPCO-specific columns (cs_nm/addr).
            # To remain resilient against schema drift we select stable columns
            # and map them to the expected keys in Python.
            # Note: production DB uses PostGIS `location` (geometry/point) and columns `name`/`address`.
            # Use ST_Y(location) for latitude and ST_X(location) for longitude. Keep COALESCE for address/name.
            # Try a spatial query (PostGIS). If the DB does not support PostGIS or
            # the `location` column is missing, fall back to a name/address LIKE query.
            spatial_query = """
                SELECT DISTINCT
                    cs_id as station_id,
                    COALESCE(address, '') as addr,
                    COALESCE(name, '') as station_name,
                    ST_Y(location)::text as lat,
                    ST_X(location)::text as lon,
                    -- compute distance in meters on DB side for accurate ordering/filtering
                    ROUND(ST_Distance(location::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography))::int as distance_m
                FROM stations
                WHERE location IS NOT NULL
                  AND ST_DWithin(
                      location::geography,
                      ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                      :radius_m
                  )
                ORDER BY distance_m
                LIMIT 100
            """

            # Fallback query when spatial support is unavailable
            fallback_name_query = """
                SELECT DISTINCT
                    cs_id as station_id,
                    COALESCE(address, '') as addr,
                    COALESCE(name, '') as station_name,
                    ST_Y(location)::text as lat,
                    ST_X(location)::text as lon,
                    ROUND(ST_Distance(location::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography))::int as distance_m
                FROM stations
                WHERE (COALESCE(address, '') LIKE :addr_pattern OR COALESCE(name, '') LIKE :addr_pattern)
                AND location IS NOT NULL
                ORDER BY distance_m
                LIMIT 100
            """

            try:
                # pass the normalized radius to the spatial query
                result = await db.execute(
                    text(spatial_query),
                    {"lon": lon_float, "lat": lat_float, "radius_m": actual_radius}
                )
            except Exception:
                # If spatial query fails (no PostGIS or column differences), fallback
                result = await db.execute(
                    text(fallback_name_query),
                    {
                        "addr_pattern": f"%{addr.split()[0] if addr else '서울'}%",
                        "lon": lon_float,
                        "lat": lat_float
                    }
                )
            db_stations = result.fetchall()
            
            if db_stations:
                print(f"✅ DB Hit: {len(db_stations)}개 충전소 발견")
                
                db_result = []
                for row in db_stations:
                    try:
                        row_dict = row._mapping
                        # prefer DB-calculated distance_m when available (faster and consistent)
                        db_distance = row_dict.get("distance_m")
                        try:
                            dist_val = int(db_distance) if db_distance is not None else int(calculate_distance_haversine(
                                lat_float, lon_float, float(row_dict["lat"]), float(row_dict["lon"])
                            ))
                        except Exception:
                            dist_val = int(calculate_distance_haversine(lat_float, lon_float, float(row_dict["lat"]), float(row_dict["lon"])))

                        if dist_val <= radius:
                            db_result.append({
                                "station_id": str(row_dict["station_id"]),
                                "addr": str(row_dict["addr"]),
                                "station_name": str(row_dict["station_name"]),
                                "lat": str(row_dict["lat"]),
                                "lon": str(row_dict["lon"]),
                                # ensure distance is returned as string (frontend expects string)
                                "distance_m": str(int(dist_val))
                            })
                    except Exception as row_error:
                        print(f"⚠️ DB row 처리 오류: {row_error}")
                        continue
                
                if db_result:
                    # sort by distance (and log a small sample for debugging radius handling)
                    db_result.sort(key=lambda x: calculate_distance_haversine(
                        lat_float, lon_float, float(x["lat"]), float(x["lon"])
                    ))
                    try:
                        distances = [int(x.get("distance_m") or calculate_distance_haversine(lat_float, lon_float, float(x["lat"]), float(x["lon"]))) for x in db_result]
                        sample = distances[:10]
                        print(f"🔍 Debug distances sample (meters): count={len(distances)} sample={sample}")
                    except Exception as _dist_err:
                        print(f"⚠️ 거리 디버그 생성 실패: {_dist_err}")
                    
                    # Cache에 저장
                    try:
                        # don't cache empty results
                        if db_result:
                            cache_data = {"stations": _serialize_for_cache(db_result), "timestamp": datetime.now(timezone.utc).isoformat()}
                            await redis_client.setex(cache_key, settings.CACHE_EXPIRE_SECONDS, json.dumps(_serialize_for_cache(cache_data), ensure_ascii=False))
                            print(f"✅ DB 결과 Cache 저장 완료: key={cache_key} ttl={settings.CACHE_EXPIRE_SECONDS}s")
                        else:
                            print(f"ℹ️ DB 결과 빈 리스트 - 캐시 저장 생략: key={cache_key}")
                    except Exception as _c_err:
                        print(f"⚠️ Cache 저장 실패: {_c_err}")
                        pass
                    
                    return {
                        "source": "database",
                        "addr": addr,
                        "radius_normalized": actual_radius,
                        "stations": db_result
                    }
        except Exception as db_error:
            # If a DB error occurs, rollback the session so subsequent DB commands
            # (e.g. inserts) are not run inside an aborted transaction.
            try:
                await db.rollback()
            except Exception:
                pass
            print(f"⚠️ DB 조회 오류: {db_error}")
        
        # === 5단계: API 호출 및 저장 ===
        print(f"✅ KEPCO API 호출 시작...")
        # use module-level `settings` imported at top to avoid UnboundLocalError
        kepco_url = settings.EXTERNAL_STATION_API_BASE_URL
        kepco_key = settings.EXTERNAL_STATION_API_KEY
        
        if not kepco_url or not kepco_key:
            raise HTTPException(status_code=500, detail="KEPCO API 설정 누락")
        
        print(f"✅ KEPCO URL: {kepco_url}")
        print(f"✅ Making KEPCO API request to: {kepco_url}")
        
        async with httpx.AsyncClient() as client:
            kepco_response = await client.get(
                kepco_url,
                params={
                    "addr": addr,
                    "apiKey": kepco_key,
                    "returnType": "json"
                },
                timeout=30.0
            )
            
            print(f"✅ KEPCO Response Status: {kepco_response.status_code}")
            
            if kepco_response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"KEPCO API 오류: HTTP {kepco_response.status_code}"
                )
            
            kepco_data = kepco_response.json()
            print(f"✅ KEPCO API 응답 수신 완료")
        
        # === 6단계: 데이터 처리 및 DB 저장 ===
        api_stations = []
        now = datetime.now(timezone.utc)
        
        if isinstance(kepco_data, dict) and "data" in kepco_data:
            raw_data = kepco_data["data"]
            
            if isinstance(raw_data, list):
                for item in raw_data:
                    try:
                        item_lat = float(item.get("lat", 0))
                        item_lon = float(item.get("longi", 0))
                        
                        if item_lat == 0 or item_lon == 0:
                            continue
                        
                        dist = calculate_distance_haversine(lat_float, lon_float, item_lat, item_lon)
                        if dist > radius:
                            continue
                        
                        station_data = {
                            "station_id": str(item.get("csId", "")),
                            "addr": str(item.get("addr", "")),
                            "station_name": str(item.get("csNm", "")),
                            "lat": str(item_lat),
                            "lon": str(item_lon),
                            "distance_m": str(int(dist))
                        }
                        api_stations.append(station_data)
                        
                        # DB에 저장 (정적 데이터) - 안전한 방식
                        try:
                            # Ensure we are not in an aborted transaction from an earlier error
                            await _clear_db_transaction(db)

                            # Use PostGIS location column. Some DBs don't have lat/long columns.
                            insert_sql = """
                                INSERT INTO stations (cs_id, address, name, location, raw_data, stat_update_datetime)
                                VALUES (:cs_id, :address, :name, ST_SetSRID(ST_MakePoint(:longi, :lat), 4326), :raw_data, :update_time)
                                ON CONFLICT (cs_id) DO UPDATE SET
                                    address = EXCLUDED.address,
                                    name = EXCLUDED.name,
                                    location = EXCLUDED.location,
                                    raw_data = EXCLUDED.raw_data,
                                    stat_update_datetime = EXCLUDED.stat_update_datetime
                            """
                            
                            await db.execute(text(insert_sql), {
                                "cs_id": item.get("csId"),
                                "address": item.get("addr"),
                                "name": item.get("csNm"),
                                "lat": item_lat,
                                "longi": item_lon,
                                "raw_data": json.dumps(item, ensure_ascii=False),
                                "update_time": now
                            })
                        except Exception as insert_error:
                            # If insert fails, rollback so the session is usable for later operations
                            try:
                                await _clear_db_transaction(db)
                            except Exception:
                                pass
                            print(f"⚠️ DB 저장 오류: {insert_error}")
                    
                    except Exception as item_error:
                        print(f"⚠️ Item 처리 오류: {item_error}")
                        continue
                
                # 트랜잭션 커밋
                try:
                    await db.commit()
                    print(f"✅ DB 저장 완료: {len(api_stations)}개 충전소")
                except Exception as commit_error:
                    print(f"⚠️ 트랜잭션 커밋 오류: {commit_error}")
                    await db.rollback()
        
        # === 7단계: Cache 저장 및 결과 반환 ===
        api_stations.sort(key=lambda x: calculate_distance_haversine(
            lat_float, lon_float, float(x["lat"]), float(x["lon"])
        ))
        # Deduplicate stations by station_id before caching/returning
        try:
            api_stations = _dedupe_stations_by_id(api_stations)
        except Exception:
            pass

        try:
            # Avoid caching empty API results
            if api_stations:
                cache_data = {"stations": _serialize_for_cache(api_stations), "timestamp": now.isoformat()}
                await redis_client.setex(cache_key, settings.CACHE_EXPIRE_SECONDS, json.dumps(_serialize_for_cache(cache_data), ensure_ascii=False))
                print(f"✅ API 결과 Cache 저장 완료: key={cache_key} ttl={settings.CACHE_EXPIRE_SECONDS}s")
            else:
                print(f"ℹ️ API 결과 빈 리스트 - 캐시 저장 생략: key={cache_key}")
        except Exception as _c_err:
            print(f"⚠️ API 캐시 저장 실패: {_c_err}")
            pass

        return {
            "source": "kepco_api",
            "addr": addr,
            "radius_normalized": actual_radius,
            "stations": api_stations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"🚨 전체 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def calculate_distance_haversine(lat1, lon1, lat2, lon2):
    """하버사인 공식으로 두 지점 간 거리 계산 (미터)"""
    try:
        R = 6371000  # 지구 반지름(미터)
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))
    except:
        return 999999


def _dedupe_stations_by_id(stations):
    """Deduplicate station dicts by station_id.

    - stations: list of dicts that must contain 'station_id' (string)
    - Returns a list preserving the first-seen station for each id but
      merges charger lists if present.
    """
    by_id = {}
    for s in stations:
        sid = str(s.get("station_id", "")).strip()
        if not sid:
            # keep as-is (no id) using a generated key
            key = f"_noid_{len(by_id)}"
            by_id[key] = s
            continue

        if sid not in by_id:
            # shallow copy to avoid mutating input
            by_id[sid] = dict(s)
        else:
            # merge non-empty fields
            existing = by_id[sid]
            for k, v in s.items():
                if k == "chargers":
                    # merge charger lists uniquely by charger_id
                    existing_ch = existing.get("chargers") or []
                    new_ch = v or []
                    seen = {c.get("charger_id") for c in existing_ch}
                    for c in new_ch:
                        if c.get("charger_id") not in seen:
                            existing_ch.append(c)
                            seen.add(c.get("charger_id"))
                    existing["chargers"] = existing_ch
                else:
                    # prefer existing non-empty value, otherwise take new
                    if not existing.get(k) and v:
                        existing[k] = v

    return list(by_id.values())


async def _clear_db_transaction(db: AsyncSession):
    """Ensure the DB session is not in an aborted transaction state.

    Calling rollback when no transaction is active is harmless; this
    is a defensive helper used before attempting writes so we don't
    hit InFailedSQLTransactionError caused by a prior failure.
    """
    try:
        await db.rollback()
    except Exception:
        # swallow - best effort only
        pass


async def _ensure_station_db_id(db: AsyncSession, cs_id: str, item: dict = None, now: datetime = None):
    """Ensure a station row exists for given cs_id and return its DB primary key id.

    If the station exists, returns the id. If not, attempts to INSERT the station
    (using provided `item` for fields) and RETURNING id. This centralizes the
    logic so callers inserting chargers never omit the required station_id FK.
    """
    if not cs_id:
        return None

    try:
        res = await db.execute(text("SELECT id FROM stations WHERE cs_id = :cs_id LIMIT 1"), {"cs_id": cs_id})
        row = res.fetchone()
        if row and row._mapping.get("id"):
            return row._mapping.get("id")
    except Exception:
        # best-effort: clear transaction and continue to attempt insert
        try:
            await _clear_db_transaction(db)
        except Exception:
            pass

    # attempt to insert station using available item data (if any)
    try:
        if now is None:
            now = datetime.now(timezone.utc)

        insert_sql = """
            INSERT INTO stations (cs_id, name, address, location, raw_data, stat_update_datetime)
            VALUES (:cs_id, :name, :address, ST_SetSRID(ST_MakePoint(:longi, :lat), 4326), :raw_data, :update_time)
            ON CONFLICT (cs_id) DO UPDATE SET
                name = COALESCE(EXCLUDED.name, stations.name),
                address = COALESCE(EXCLUDED.address, stations.address),
                location = COALESCE(EXCLUDED.location, stations.location),
                raw_data = COALESCE(EXCLUDED.raw_data, stations.raw_data),
                stat_update_datetime = COALESCE(EXCLUDED.stat_update_datetime, stations.stat_update_datetime)
            RETURNING id
        """

        params = {
            "cs_id": cs_id,
            "name": (item.get("csNm") if item else None) or (item.get("cs_nm") if item else None) or None,
            "address": (item.get("addr") if item else None) or None,
            "lat": float(item.get("lat")) if item and item.get("lat") else None,
            "longi": float(item.get("longi")) if item and item.get("longi") else None,
            "raw_data": json.dumps(item, ensure_ascii=False) if item else None,
            "update_time": now
        }

        await _clear_db_transaction(db)
        r = await db.execute(text(insert_sql), params)
        row = r.fetchone()
        if row and row._mapping.get("id"):
            return row._mapping.get("id")
    except Exception as e:
        try:
            await _clear_db_transaction(db)
        except Exception:
            pass
        print(f"⚠️ _ensure_station_db_id 실패: {e}")

    return None


def _serialize_for_cache(obj):
    """Recursively convert common non-JSON types to JSON-serializable values.

    Handles datetime -> ISO string, dicts, lists. Keeps other primitives unchanged.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize_for_cache(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_for_cache(v) for v in obj]
    return obj

@app.get("/api/v1/stations-kepco-2025", tags=["Station"], summary="🚀 KEPCO 2025 API - BRAND NEW")
async def kepco_2025_new_api_implementation(
    lat: float = Query(..., description="위도 좌표", ge=-90, le=90),
    lon: float = Query(..., description="경도 좌표", ge=-180, le=180), 
    radius: int = Query(..., description="검색 반경(미터) - 필수", ge=100, le=10000),
    page: int = Query(1, description="페이지 번호", ge=1),
    limit: int = Query(20, description="페이지당 결과 수", ge=1, le=100),
    api_key: str = Depends(frontend_api_key_required),
    db: AsyncSession = Depends(get_async_session),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    🚀 KEPCO 2025 API - 완전히 새로운 구현
    이전 URL: /ws/chargePoint/curChargePoint (삭제됨)
    새 URL: /EVchargeManage.do (정확함)
    """
    print(f"🚀🚀🚀 KEPCO 2025 COMPLETELY NEW CODE 🚀🚀🚀")
    print(f"🚀 Function: kepco_2025_new_api_implementation")
    print(f"🚀 Time: {datetime.now(timezone.utc)}")
    print(f"🚀 Params: lat={lat}, lon={lon}, radius={radius}")
    print(f"🚀 ABSOLUTE CONFIRMATION: This is the NEW CODE running!")
    print(f"🚀 Expected KEPCO URL: https://bigdata.kepco.co.kr/openapi/v1/EVchargeManage.do")
    
    try:
        # === 직접 KEPCO API 호출 (단순화) ===
        from app.core.config import settings
        
        # 좌표 → 주소 변환 (Nominatim 역지오코딩 사용)
        # 이전에 하드코딩된 '서울특별시 강남구' 때문에 입력 좌표와 무관하게 결과가 나오는 문제가 있었습니다.
        # 여기서 실제로 lat/lon을 역지오코딩해서 KEPCO API의 addr 파라미터로 사용합니다.
        try:
            async with httpx.AsyncClient() as client:
                nomi_resp = await client.get(
                    "https://nominatim.openstreetmap.org/reverse",
                    params={"lat": lat, "lon": lon, "format": "json", "addressdetails": 1, "accept-language": "ko"},
                    headers={"User-Agent": "Codyssey-EV-App/1.0"},
                    timeout=10.0
                )
                if nomi_resp.status_code == 200:
                    nomi_json = nomi_resp.json()
                    addr_comp = nomi_json.get("address", {}) if isinstance(nomi_json, dict) else {}
                    city = addr_comp.get("city") or addr_comp.get("town") or ""
                    district = addr_comp.get("borough") or addr_comp.get("suburb") or ""
                    search_addr = f"{city} {district}".strip()
                    if not search_addr:
                        # fallback to display_name or coordinate string
                        search_addr = nomi_json.get("display_name") if isinstance(nomi_json, dict) else f"{lat},{lon}"
                else:
                    search_addr = f"{lat},{lon}"
        except Exception:
            # Any failure in geocoding should not block KEPCO call; use coordinate fallback
            search_addr = f"{lat},{lon}"
        
        # KEPCO API 설정
        kepco_url = settings.EXTERNAL_STATION_API_BASE_URL
        kepco_key = settings.EXTERNAL_STATION_API_KEY
        
        print(f"🚀 KEPCO URL: {kepco_url}")
        print(f"🚀 KEPCO KEY: {kepco_key[:10] if kepco_key else 'None'}...")
        print(f"🚀 Search Address: {search_addr}")
        
        if not kepco_url or not kepco_key:
            print(f"🚨 KEPCO 설정 오류!")
            raise HTTPException(status_code=500, detail="KEPCO API 설정 누락")
        
        # KEPCO API 직접 호출
        async with httpx.AsyncClient() as client:
            print(f"🚀 Calling KEPCO API...")
            kepco_response = await client.get(
                kepco_url,
                params={
                    "addr": search_addr,
                    "apiKey": kepco_key,
                    "returnType": "json"
                },
                timeout=30.0
            )
            
            print(f"🚀 KEPCO Response Status: {kepco_response.status_code}")
            
            if kepco_response.status_code != 200:
                print(f"🚨 KEPCO API 오류: {kepco_response.status_code}")
                print(f"🚨 Response: {kepco_response.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"KEPCO API 오류: HTTP {kepco_response.status_code}"
                )
            
            kepco_data = kepco_response.json()
            print(f"🚀 KEPCO Data Type: {type(kepco_data)}")
            print(f"🚀 KEPCO Data Keys: {kepco_data.keys() if isinstance(kepco_data, dict) else 'Not dict'}")
        
        # 거리 계산 함수
        def calculate_distance(lat1, lon1, lat2, lon2):
            try:
                R = 6371000  # 지구 반지름(미터)
                lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
                dlat, dlon = lat2 - lat1, lon2 - lon1
                a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
                return R * 2 * math.asin(math.sqrt(a))
            except:
                return 999999
        
        # 데이터 처리
        stations = []
        if isinstance(kepco_data, dict) and "data" in kepco_data:
            raw_data = kepco_data["data"]
            print(f"🚀 Found {len(raw_data) if isinstance(raw_data, list) else 0} stations from KEPCO")
            
            if isinstance(raw_data, list):
                # process all returned stations from KEPCO, then sort and limit
                for item in raw_data:
                    try:
                        slat = float(item.get("lat", 0))
                        slon = float(item.get("longi", 0))
                        
                        if slat == 0 or slon == 0:
                            continue
                        
                        # 거리 확인
                        dist = calculate_distance(lat, lon, slat, slon)
                        # ensure numeric distance and use radius filter
                        try:
                            if dist is None:
                                continue
                            if dist > radius:
                                continue
                        except Exception:
                            continue
                        
                        stations.append({
                            "station_id": item.get("csId", ""),
                            "station_name": item.get("csNm", ""),
                            "address": item.get("addr", ""),
                            "lat": slat,
                            "lon": slon,
                            "distance_m": int(dist),
                            "charger_id": item.get("cpId", ""),
                            "charger_name": item.get("cpNm", ""),
                            "status": item.get("cpStat", ""),
                            "type": item.get("chargeTp", "")
                        })
                    except Exception as item_error:
                        print(f"🚨 Item processing error: {item_error}")
                        continue
        
        # Deduplicate stations by station_id then sort and return
        try:
            stations = _dedupe_stations_by_id(stations)
        except Exception:
            pass

        # 결과 정렬 및 반환: sort by numeric distance and then apply limit
        try:
            stations.sort(key=lambda x: int(x.get("distance_m") or 999999))
        except Exception:
            try:
                stations.sort(key=lambda x: x.get("distance_m") or 999999)
            except Exception:
                pass
        final_result = stations[:limit]
        
        print(f"🚀 Final result: {len(final_result)} stations")
        
        return {
            "message": "🚀 KEPCO 2025 NEW API SUCCESS!",
            "status": "kepco_2025_success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "search_params": {
                "lat": lat,
                "lon": lon,
                "radius": radius,
                "search_address": search_addr
            },
            "result_info": {
                "total_found": len(stations),
                "returned": len(final_result)
            },
            "stations": final_result
        }
    except Exception as e:
        print(f"🚨 KEPCO 2025 ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"KEPCO 검색 실패: {str(e)}")


# --- V1 API 라우터 포함 (일반 사용자 접근 가능) ---
app.include_router(api_router, prefix="/api/v1")

# --- 관리자 전용 엔드포인트 ---
admin_router = APIRouter(dependencies=[Depends(admin_required)])

@admin_router.get("/admin-only-data")
async def admin_data():
    return {"msg": "관리자 전용 데이터입니다."}


# Admin: Redis key inspection (dry-run only, no delete)
@admin_router.get("/redis/keys", summary="관리자: Redis 키 조회 (삭제하지 않음)")
async def admin_redis_keys(pattern: str = Query("stations:*", description="SCAN 패턴 (예: stations:*)"),
                           count: int = Query(100, description="SCAN count hint"),
                           redis_client: Redis = Depends(get_redis_client)):
    """관리자 전용: Redis에서 패턴에 맞는 키를 나열합니다. 삭제는 수행하지 않습니다.

    보호: 이 엔드포인트는 `admin_required` 의존성으로 보호됩니다. Render에서 직접 호출하거나
    관리자 자격증명을 사용해 호출하세요.
    """
    if not redis_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis client is not available")

    keys = []
    try:
        # async scan_iter is supported by redis.asyncio
        async for k in redis_client.scan_iter(match=pattern, count=count):
            keys.append(k)
            # limit returned keys to avoid huge payloads
            if len(keys) >= 1000:
                break
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis scan failed: {e}")

    return {"pattern": pattern, "count": len(keys), "keys": keys}


@admin_router.get("/redis/debug", summary="관리자: Redis 디버그 정보 (ping/info)")
async def admin_redis_debug(redis_client: Redis = Depends(get_redis_client)):
    """Admin-only endpoint that returns Redis connectivity and a small INFO summary.

    Protected by admin_required via admin_router. Use this to quickly verify which
    Redis instance the application is talking to and basic memory/client stats.
    """
    if not redis_client:
        return JSONResponse(status_code=503, content={"ok": False, "reason": "redis_unavailable"})
    try:
        ping = await redis_client.ping()
    except Exception as e:
        return JSONResponse(status_code=503, content={"ok": False, "reason": f"ping_failed: {e}"})

    # Try to fetch small subset of INFO keys
    info_summary = {}
    try:
        info = await redis_client.info()
        info_summary = {
            "role": info.get("role"),
            "used_memory_human": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
        }
    except Exception as _:
        info_summary = {"ok": False, "reason": "info_unavailable"}

    # count a small sample of keys in station_detail namespace
    key_count = None
    try:
        # This is a potentially expensive operation on large datasets; limit by count.
        cnt = 0
        async for _k in redis_client.scan_iter(match="station_detail:*", count=100):
            cnt += 1
            if cnt >= 1000:
                break
        key_count = cnt
    except Exception:
        key_count = None

    return {
        "ok": True,
        "ping": bool(ping),
        "info": info_summary,
        "station_detail_key_sample_count": key_count
    }


# Register admin_router AFTER all admin routes have been defined so every
# admin endpoint (e.g. /admin/redis/debug) is included. Previously the
# router was registered too early which caused routes defined afterwards
# to be omitted from the app and OpenAPI.
app.include_router(admin_router, prefix="/admin")


# Startup diagnostic: log registered routes so we can verify deployed route registration
@app.on_event("startup")
async def _log_registered_routes_on_startup():
    try:
        route_paths = sorted({r.path for r in app.routes})
        print(f"🛠️ Registered routes count={len(route_paths)}")
        # print a compact sample of admin routes
        admin_routes = [p for p in route_paths if p.startswith("/admin")]
        print(f"🛠️ Admin routes ({len(admin_routes)}): {admin_routes}")
        # explicit check for the specific debug path we expect
        target = "/admin/redis/debug"
        if target in route_paths:
            print(f"✅ Startup check: {target} is REGISTERED")
        else:
            print(f"❌ Startup check: {target} is MISSING (this explains 404 responses)")
        # also log whether OpenAPI is exposed
        print(f"🛠️ openapi_url={app.openapi_url}")
    except Exception as e:
        print(f"⚠️ Failed to enumerate routes on startup: {e}")


# Internal debug endpoint (protected by DEBUG_TOKEN env var). This is temporary and
# should be removed after investigation. Returns registered routes and admin flags.
@app.get("/internal/debug/admin-routes", include_in_schema=False)
async def _internal_debug_admin_routes(x_debug_token: Optional[str] = Header(None)):
    """Return minimal runtime info about registered routes.

    Protection: requires environment variable DEBUG_TOKEN to be set on the server
    and the same value sent in header `X-Debug-Token`.
    If DEBUG_TOKEN is not set, the endpoint reports that it is disabled.
    """
    debug_token = os.getenv("DEBUG_TOKEN", "")
    if not debug_token:
        return JSONResponse(status_code=404, content={"ok": False, "reason": "debug_token_not_configured"})

    if not x_debug_token or x_debug_token != debug_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Compact list of routes (strings)
    try:
        route_paths = sorted({r.path for r in app.routes})
    except Exception:
        route_paths = [r.path for r in app.routes]

    return {
        "ok": True,
        "is_admin_mode": IS_ADMIN,
        "openapi_url": app.openapi_url,
        "routes": route_paths
    }




# --- DB 연결 테스트 / 간단 조회 엔드포인트 ---
@app.get("/db-test", tags=["Infrastructure"], summary="DB 연결 및 보조금(subsidy) 조회 테스트")
async def db_test_endpoint(manufacturer: str, model_group: str, db: AsyncSession = Depends(get_async_session), _ok: bool = Depends(frontend_api_key_required)):
    """제조사(manufacturer)와 모델그룹(model_group)을 받아 `subsidies` 테이블을 조회합니다.

    이 엔드포인트는 OpenAPI 문서에서 두 개의 문자열 쿼리 파라미터로 노출됩니다.
    """
    _ok: bool = Depends(frontend_api_key_required)
    start_time = time.time()
    try:
        # 안전한 파라미터 바인딩으로 쿼리 실행
        query_sql = (
            "SELECT model_name, subsidy_national_10k_won, subsidy_local_10k_won, subsidy_total_10k_won "
            "FROM subsidies "
            "WHERE manufacturer = :manufacturer AND model_group = :model_group LIMIT 50"
        )
        ensure_read_only_sql(query_sql)
        result = await db.execute(text(query_sql), {"manufacturer": manufacturer, "model_group": model_group})
        rows = result.fetchall()

        response_time_ms = (time.time() - start_time) * 1000
        # Map DB columns to frontend-friendly Korean keys
        mapped_rows = []
        for row in rows:
            m = row._mapping
            mapped_rows.append({
                "모델명": m.get("model_name"),
                "국비(만원)": m.get("subsidy_national_10k_won"),
                "지방비(만원)": m.get("subsidy_local_10k_won"),
                "보조금(만원)": m.get("subsidy_total_10k_won"),
            })

        return {
            "message": "Database query executed",
            "status": "ok",
            "manufacturer": manufacturer,
            "model_group": model_group,
            "count": len(mapped_rows),
            "rows": mapped_rows,
            "response_time_ms": f"{response_time_ms:.2f}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database query failed: {e.__class__.__name__}: {e}"
        )


# --- Redis 연결 테스트 엔드포인트 ---
@app.get("/redis-test", tags=["Infrastructure"], summary="Redis 캐시 연결 테스트")
async def redis_test_endpoint(redis_client: Redis = Depends(get_redis_client)):
    if not redis_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis client is not initialized or connected.")
    test_key = "infra:test:key"
    test_data = {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
    try:
        await set_cache(test_key, test_data, expire=10)
        retrieved_data = await get_cache(test_key)
        if retrieved_data and retrieved_data["status"] == "ok":
            return {"message": "Redis connection test successful!", "data_stored": test_data, "data_retrieved": retrieved_data, "status": "ok"}
        else:
            raise Exception("Data mismatch or retrieval failed.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Redis operation FAILED!: {e.__class__.__name__}: {e}")


# --- 충전소 아이콘 클릭 → 충전기 스펙 조회 엔드포인트 ---
@app.get("/api/v1/station/{station_id}/chargers", tags=["Station"], summary="✅ 충전기 스펙 조회 (요구사항 준수)")
async def get_station_charger_specs(
    station_id: str = Path(..., description="충전소ID (string 타입)"),
    addr: str = Query(..., description="충전기주소 (string 타입)"),
    api_key: str = Depends(frontend_api_key_required),
    db: AsyncSession = Depends(get_async_session),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    ✅ 요구사항 2번 - 충전소 아이콘 클릭 → 충전기 스펙 조회
    
    1. 프론트 요청: 충전소ID, 충전기주소(addr), API KEY (모두 string)
    2. 백엔드 로직: DB검색(충전소ID) → API검색(addr) → 캐시 반영 & 동적 데이터 갱신
    3. 응답: 충전소명칭, 제공가능한충전방식, 각 충전기 정보(상태코드+충전방식 매핑)
    """
    print(f"✅ 충전기 스펙 조회 시작")
    print(f"✅ station_id={station_id}, addr={addr}")
    
    try:
        # === 1단계: DB 조회 (충전소ID 활용) - 안전한 쿼리 ===
        print(f"✅ DB에서 충전소 정보 조회...")
        
        # 정적 데이터 조회
        # Try a richer query that uses `static_data_updated_at` if present; if the
        # column is missing (ProgrammingError) fallback to a simpler query. Also
        # ensure we rollback any aborted transaction before retrying.
        primary_station_query = """
         SELECT id as station_db_id, cs_id, COALESCE(name, '') AS cs_nm, COALESCE(address, '') AS addr,
             ST_Y(location)::text AS lat, ST_X(location)::text AS longi,
             COALESCE(static_data_updated_at, updated_at) AS last_updated,
             -- most recent charger dynamic update time for this station
             (SELECT MAX(stat_update_datetime) FROM chargers WHERE cs_id = stations.cs_id) AS last_charger_update
         FROM stations
         WHERE cs_id = :station_id
         LIMIT 1
     """

        fallback_station_query = """
         SELECT id as station_db_id, cs_id, COALESCE(name, '') AS cs_nm, COALESCE(address, '') AS addr,
             ST_Y(location)::text AS lat, ST_X(location)::text AS longi,
             updated_at AS last_updated,
             (SELECT MAX(stat_update_datetime) FROM chargers WHERE cs_id = stations.cs_id) AS last_charger_update
         FROM stations
         WHERE cs_id = :station_id
         LIMIT 1
     """

        station_row = None
        try:
            try:
                station_result = await db.execute(text(primary_station_query), {"station_id": station_id})
                station_row = station_result.fetchone()
            except ProgrammingError as pe:
                # Column missing or other programming error — clear transaction and retry with fallback
                try:
                    await _clear_db_transaction(db)
                except Exception:
                    pass
                print(f"⚠️ Primary station query ProgrammingError, falling back: {pe}")
                try:
                    station_result = await db.execute(text(fallback_station_query), {"station_id": station_id})
                    station_row = station_result.fetchone()
                except Exception as fallback_err:
                    try:
                        await _clear_db_transaction(db)
                    except Exception:
                        pass
                    print(f"⚠️ Fallback station query failed: {fallback_err}")
                    station_row = None
            except Exception as station_db_error:
                # Other DB error: clear and continue
                try:
                    await _clear_db_transaction(db)
                except Exception:
                    pass
                print(f"⚠️ DB 조회 오류(충전소 상세): {station_db_error}")
                station_row = None
        finally:
            # ensure we aren't leaving an aborted transaction open
            try:
                await _clear_db_transaction(db)
            except Exception:
                pass
        
        if not station_row:
            print(f"⚠️ DB에서 충전소 정보 없음, API 호출로 진행")
            station_info = None
        else:
            station_dict = station_row._mapping
            # Normalize any datetime-like fields to ISO strings to make caching/JSON safe
            def _dt_to_iso(val):
                try:
                    if isinstance(val, datetime):
                        return val.isoformat()
                    return val
                except Exception:
                    return None

            # Preserve the raw DB datetime for charger-level latest update so we
            # can perform accurate freshness comparisons (avoid converting to
            # ISO string too early). We still present ISO strings when caching
            # or returning JSON, but internal logic uses datetime objects.
            station_info = {
                "station_db_id": station_dict.get("station_db_id"),
                "station_id": str(station_dict["cs_id"]),
                "station_name": str(station_dict["cs_nm"]),
                "addr": str(station_dict["addr"]),
                "lat": str(station_dict["lat"]),
                "lon": str(station_dict["longi"]),
                # keep last_updated as ISO for informational purposes
                "last_updated": _dt_to_iso(station_dict.get("stat_update_datetime")),
                # keep raw DB value (may be datetime or string) for freshness check
                "last_charger_update": station_dict.get("last_charger_update")
            }
            print(f"✅ DB에서 충전소 정보 발견: {station_info['station_name']}")

        # === Redis 캐시 우선 검사 (30분 이내인 경우 바로 반환) ===
        try:
            cache_key = f"station_detail:{station_id}"
            cached_blob = None
            if redis_client:
                cached_raw = await redis_client.get(cache_key)
                if cached_raw:
                    try:
                        cached_blob = json.loads(cached_raw)
                    except Exception:
                        cached_blob = None

                if cached_blob and isinstance(cached_blob, dict) and cached_blob.get("timestamp"):
                    # Robust parsing of cached timestamp:
                    # - Accept ISO with and without timezone
                    # - Accept ISO with trailing 'Z' (convert to +00:00)
                    # - Accept legacy compact format YYYYMMDDHHMMSS
                    def _parse_cached_ts(raw_ts):
                        if raw_ts is None:
                            return None
                        s = str(raw_ts)
                        # Handle trailing Z (UTC)
                        if s.endswith("Z"):
                            s = s[:-1] + "+00:00"
                        try:
                            parsed = datetime.fromisoformat(s)
                            # Treat naive datetimes as UTC for cache age calculations
                            if parsed.tzinfo is None:
                                parsed = parsed.replace(tzinfo=timezone.utc)
                            return parsed
                        except Exception:
                            # Try legacy compact format: YYYYMMDDHHMMSS
                            try:
                                parsed = datetime.strptime(s, "%Y%m%d%H%M%S")
                                return parsed.replace(tzinfo=timezone.utc)
                            except Exception:
                                return None

                    cached_ts = _parse_cached_ts(cached_blob.get("timestamp"))
                    if cached_ts is None:
                        print("⚠️ Redis 캐시의 timestamp 파싱 실패 - 무시하고 API/DB 검사 진행")
                    else:
                        age_min = (datetime.now(timezone.utc) - cached_ts).total_seconds() / 60
                        # use configured detail TTL for cache acceptance (seconds -> minutes)
                        detail_ttl_min = getattr(settings, "CACHE_DETAIL_EXPIRE_SECONDS", 300) / 60
                        if age_min <= detail_ttl_min:
                            print(f"✅ Redis 캐시 사용: station_detail:{station_id} age={age_min:.1f}min (ttl_min={detail_ttl_min:.1f})")
                            # normalize cached payload to the endpoint response shape
                            cached_station_info = cached_blob.get("station_info") or {}
                            cached_chargers = cached_blob.get("chargers") or []
                            cached_available = cached_blob.get("available_charge_types") or []
                            resp = {
                                "station_name": cached_station_info.get("station_name") or cached_station_info.get("cs_nm") or "",
                                "available_charge_types": ", ".join(cached_available),
                                "charger_details": cached_chargers,
                                "total_chargers": len(cached_chargers),
                                "source": "cache",
                                "timestamp": cached_blob.get("timestamp")
                            }
                            return JSONResponse(status_code=200, content=resp)
                        else:
                            print(f"ℹ️ Redis 캐시 존재하지만 만료 기준 초과(age={age_min:.1f}min) - API/DB 검사 진행")
        except Exception as cache_err:
            print(f"⚠️ Redis 조회 오류(무시): {cache_err}")

        # === 2단계: 충전기 동적 데이터 갱신 체크 (30분 규칙) ===
        need_api_call = True
        cached_chargers = []

        if station_info:
            # Use the latest charger-level update timestamp (not static station timestamp)
            now = datetime.now(timezone.utc)
            last_charger_update = station_info.get("last_charger_update")

            # Normalize last_charger_update into a datetime object if possible.
            last_charger_update_dt = None
            if last_charger_update:
                if isinstance(last_charger_update, datetime):
                    # If the DB returned a naive datetime, treat it as UTC to avoid
                    # arithmetic errors when comparing with timezone-aware 'now'.
                    if last_charger_update.tzinfo is None:
                        last_charger_update_dt = last_charger_update.replace(tzinfo=timezone.utc)
                    else:
                        last_charger_update_dt = last_charger_update
                else:
                    # If DB layer returned a string (ISO) try to parse it.
                    try:
                        parsed = datetime.fromisoformat(str(last_charger_update))
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=timezone.utc)
                        last_charger_update_dt = parsed
                    except Exception:
                        # Could not parse — leave as None which triggers API call
                        last_charger_update_dt = None

            if last_charger_update_dt:
                # Compute difference in minutes robustly: ensure both sides are timezone-aware
                def _ensure_aware(dt_val):
                    try:
                        if isinstance(dt_val, datetime):
                            if dt_val.tzinfo is None:
                                return dt_val.replace(tzinfo=timezone.utc)
                            return dt_val
                        return None
                    except Exception:
                        return None

                time_diff = None
                try:
                    now_aware = _ensure_aware(now) or now
                    other_aware = _ensure_aware(last_charger_update_dt) or last_charger_update_dt
                    # final defensive attempt: coerce to timestamps if subtraction fails
                    try:
                        time_diff = (now_aware - other_aware).total_seconds() / 60
                    except Exception:
                        time_diff = (float(now_aware.timestamp()) - float(other_aware.timestamp())) / 60
                except Exception as td_err:
                    print(f"⚠️ 시간 차 계산 중 예외: {td_err} now={now} other={last_charger_update_dt}")

                if time_diff is not None:
                    if time_diff <= 30:
                        print(f"✅ 충전기 데이터가 최신임 (갱신 후 {time_diff:.1f}분), DB의 동적 데이터 사용")
                        need_api_call = False
                    else:
                        print(f"✅ 충전기 데이터가 오래됨 (갱신 후 {time_diff:.1f}분), API 호출 필요")
                else:
                    print("⚠️ 충전기 최신 업데이트 시간 비교 불가 - 안전을 위해 API 호출 진행")
            else:
                print("✅ 충전기 최신 업데이트 없음(첫 조회 또는 DB에 충전기 데이터 없음 또는 파싱 실패), API 호출 필요")

            # If DB is fresh, load charger rows to return
            if not need_api_call:
                charger_query = """
                    SELECT station_id, cp_id, cp_nm, cp_stat, charge_tp, cs_id, stat_update_datetime, kepco_stat_update_datetime
                    FROM chargers 
                    WHERE cs_id = :station_id
                    ORDER BY cp_id
                """

                charger_result = await db.execute(text(charger_query), {"station_id": station_id})
                charger_rows = charger_result.fetchall()

                for row in charger_rows:
                    row_dict = row._mapping
                    # normalize stat_update_datetime to ISO if present
                    sdt = row_dict.get("stat_update_datetime")
                    sdt_iso = sdt.isoformat() if isinstance(sdt, datetime) else sdt
                    cached_chargers.append({
                        "charger_id": str(row_dict["cp_id"]),
                        "charger_name": str(row_dict["cp_nm"]),
                        "status_code": str(row_dict.get("cp_stat") or ""),
                        "charge_type": str(row_dict.get("charge_tp") or ""),
                        "stat_update_datetime": sdt_iso,
                        "kepco_stat_update_datetime": (row_dict.get("kepco_stat_update_datetime").isoformat() if isinstance(row_dict.get("kepco_stat_update_datetime"), datetime) else row_dict.get("kepco_stat_update_datetime")),
                        "station_db_id": row_dict.get("station_id")
                    })
        
        # === 3단계: API 호출 (필요시) ===
        if need_api_call:
            print(f"✅ KEPCO API 호출로 최신 데이터 조회...")
            # use module-level `settings` imported at top
            kepco_url = settings.EXTERNAL_STATION_API_BASE_URL
            kepco_key = settings.EXTERNAL_STATION_API_KEY
            
            if not kepco_url or not kepco_key:
                raise HTTPException(status_code=500, detail="KEPCO API 설정 누락")
            
            async with httpx.AsyncClient() as client:
                kepco_response = await client.get(
                    kepco_url,
                    params={
                        "addr": addr,
                        "apiKey": kepco_key,
                        "returnType": "json"
                    },
                    timeout=30.0
                )
                
                print(f"✅ KEPCO Response Status: {kepco_response.status_code}")
                
                if kepco_response.status_code != 200:
                    # API 실패시 DB 데이터 사용
                    if cached_chargers:
                        print(f"⚠️ API 실패, 기존 DB 데이터 사용")
                    else:
                        raise HTTPException(
                            status_code=502,
                            detail=f"KEPCO API 오류: HTTP {kepco_response.status_code}"
                        )
                else:
                    kepco_data = kepco_response.json()
                    
                    # API 데이터 처리 및 DB 저장
                    if isinstance(kepco_data, dict) and "data" in kepco_data:
                        raw_data = kepco_data["data"]
                        updated_chargers = []
                        now = datetime.now(timezone.utc)
                        
                        if isinstance(raw_data, list):
                            for item in raw_data:
                                try:
                                    if str(item.get("csId", "")) == station_id:
                                        # 충전소 정보 업데이트
                                        if not station_info:
                                            station_info = {
                                                "station_id": str(item.get("csId", "")),
                                                "station_name": str(item.get("csNm", "")),
                                                "addr": str(item.get("addr", "")),
                                                "lat": str(item.get("lat", "")),
                                                "lon": str(item.get("longi", ""))
                                            }

                                        # 충전기 정보 수집 (we'll respond with these freshly fetched statuses)
                                        charger_data = {
                                            "charger_id": str(item.get("cpId", "")),
                                            "charger_name": str(item.get("cpNm", "")),
                                            "status_code": str(item.get("cpStat", "")),
                                            "charge_type": str(item.get("chargeTp", ""))
                                        }
                                        updated_chargers.append(charger_data)

                                        # DB에 저장 (동적 데이터 갱신) - set stat_update_datetime to now
                                        try:
                                            # ensure we have the station DB primary key to satisfy chargers.station_id NOT NULL
                                            station_db_id = station_info.get("station_db_id") if station_info else None
                                            # ensure station_db_id exists (create station row if necessary)
                                            if not station_db_id:
                                                station_db_id = await _ensure_station_db_id(db, str(item.get("csId")), item=item, now=now)

                                            # determine provider-side timestamp (if any) from API payload
                                            provider_ts = None
                                            provider_ts_dt = None
                                            # Try to extract and parse provider-supplied timestamp from several possible key names.
                                            for k in ("kepco_stat_update_datetime", "stat_update_datetime", "statUpdateDatetime", "statUpdate", "statUpdDt", "update_time", "update_dt", "lastUpdate", "stat_date", "stat_time", "cpStatTime"):
                                                if k in item and item.get(k):
                                                    raw_ts = item.get(k)
                                                    # Normalize to ISO UTC when possible; otherwise keep raw string for auditing.
                                                    try:
                                                        # try ISO formats first
                                                        try:
                                                            parsed = datetime.fromisoformat(str(raw_ts))
                                                            if parsed.tzinfo is None:
                                                                # assume UTC if no tz provided
                                                                parsed = parsed.replace(tzinfo=timezone.utc)
                                                            provider_ts_dt = parsed.astimezone(timezone.utc)
                                                            provider_ts = provider_ts_dt.isoformat()
                                                        except Exception:
                                                            # try common compact format YYYYMMDDHHMMSS
                                                            try:
                                                                parsed = datetime.strptime(str(raw_ts), "%Y%m%d%H%M%S")
                                                                provider_ts_dt = parsed.replace(tzinfo=timezone.utc)
                                                                provider_ts = provider_ts_dt.isoformat()
                                                            except Exception:
                                                                # fallback: stringify raw value
                                                                provider_ts = str(raw_ts)
                                                                provider_ts_dt = None
                                                    except Exception:
                                                        provider_ts = str(raw_ts)
                                                        provider_ts_dt = None
                                                    break

                                            # Log notable discrepancies between provider timestamp and server fetch time for monitoring
                                            try:
                                                if provider_ts_dt:
                                                    delta = now - provider_ts_dt
                                                    # if provider timestamp differs from server fetch by >5 minutes, log it for review
                                                    if abs(delta) > timedelta(minutes=5):
                                                        print(f"⚠️ Provider timestamp discrepancy for csId={item.get('csId')} cpId={item.get('cpId')}: provider={provider_ts_dt.isoformat()} server_fetch={now.isoformat()} delta={delta}")
                                            except Exception:
                                                # non-fatal monitoring failure
                                                pass

                                            charger_insert_sql = """
                                                INSERT INTO chargers (station_id, cp_id, cp_nm, cp_stat, charge_tp, cs_id, stat_update_datetime, kepco_stat_update_datetime)
                                                VALUES (:station_id, :cp_id, :cp_nm, :cp_stat, :charge_tp, :cs_id, :update_time, :kepco_ts)
                                                ON CONFLICT (cp_id) DO UPDATE SET
                                                    station_id = COALESCE(EXCLUDED.station_id, chargers.station_id),
                                                    cp_nm = EXCLUDED.cp_nm,
                                                    cp_stat = EXCLUDED.cp_stat,
                                                    charge_tp = EXCLUDED.charge_tp,
                                                    stat_update_datetime = EXCLUDED.stat_update_datetime,
                                                    kepco_stat_update_datetime = EXCLUDED.kepco_stat_update_datetime
                                            """
                                            # clear any prior aborted transaction
                                            try:
                                                await _clear_db_transaction(db)
                                            except Exception:
                                                pass

                                            # Ensure we have station_db_id for the foreign key constraint
                                            if station_db_id is not None:
                                                try:
                                                    await _clear_db_transaction(db)
                                                    await db.execute(text(charger_insert_sql), {
                                                        "station_id": station_db_id,
                                                        "cp_id": item.get("cpId"),
                                                        "cp_nm": item.get("cpNm"),
                                                        "cp_stat": item.get("cpStat"),
                                                        "charge_tp": item.get("chargeTp"),
                                                        "cs_id": item.get("csId"),
                                                        # stat_update_datetime stores server fetch time (now) to be used for 30-min freshness checks
                                                        "update_time": now,
                                                        # kepco_stat_update_datetime stores provider-supplied timestamp (if any) for auditing
                                                        "kepco_ts": provider_ts
                                                    })
                                                    print(f"✅ 충전기 DB 저장 성공: cp_id={item.get('cpId')}, station_id={station_db_id}")
                                                except Exception as db_err_inner:
                                                    try:
                                                        await db.rollback()
                                                    except Exception:
                                                        pass
                                                    print(f"⚠️ 충전기 DB 저장 오류: {db_err_inner}")
                                            else:
                                                # station DB id missing -> try to create station then insert charger
                                                try:
                                                    await _clear_db_transaction(db)
                                                    station_insert_sql = """
                                                        INSERT INTO stations (cs_id, name, address, location, raw_data, stat_update_datetime)
                                                        VALUES (:cs_id, :name, :address, ST_SetSRID(ST_MakePoint(:longi, :lat), 4326), :raw_data, :update_time)
                                                        ON CONFLICT (cs_id) DO UPDATE SET
                                                            name = EXCLUDED.name,
                                                            address = EXCLUDED.address,
                                                            location = EXCLUDED.location,
                                                            raw_data = EXCLUDED.raw_data,
                                                            stat_update_datetime = EXCLUDED.stat_update_datetime
                                                        RETURNING id
                                                    """
                                                    result = await db.execute(text(station_insert_sql), {
                                                        "cs_id": item.get("csId"),
                                                        "name": item.get("csNm"),
                                                        "address": item.get("addr"),
                                                        "lat": float(item.get("lat", 0)),
                                                        "longi": float(item.get("longi", 0)),
                                                        "raw_data": json.dumps(item, ensure_ascii=False),
                                                        "update_time": now
                                                    })
                                                    station_row = result.fetchone()
                                                    if station_row:
                                                        station_db_id = station_row._mapping.get("id")
                                                        print(f"✅ 충전소 생성됨: station_id={station_db_id}")
                                                        try:
                                                            await db.execute(text(charger_insert_sql), {
                                                                "station_id": station_db_id,
                                                                "cp_id": item.get("cpId"),
                                                                "cp_nm": item.get("cpNm"),
                                                                "cp_stat": item.get("cpStat"),
                                                                "charge_tp": item.get("chargeTp"),
                                                                "cs_id": item.get("csId"),
                                                                "update_time": now,
                                                                "kepco_ts": provider_ts
                                                            })
                                                            print(f"✅ 충전기 DB 저장 재시도 성공: cp_id={item.get('cpId')}")
                                                        except Exception as charger_retry_err:
                                                            try:
                                                                await db.rollback()
                                                            except Exception:
                                                                pass
                                                            print(f"⚠️ 충전기 재시도 저장 실패: {charger_retry_err}")
                                                    else:
                                                        print(f"⚠️ 충전기 DB 저장 스킵: station DB id를 찾을 수 없음 for csId={item.get('csId')}")
                                                except Exception as station_create_error:
                                                    print(f"⚠️ 충전소 생성 실패: {station_create_error}")
                                                    try:
                                                        await _clear_db_transaction(db)
                                                    except Exception:
                                                        pass
                                        except Exception as db_error:
                                            try:
                                                await db.rollback()
                                            except Exception:
                                                pass
                                            print(f"⚠️ 충전기 DB 저장 오류: {db_error}")
                                except Exception as item_error:
                                    print(f"⚠️ 충전기 데이터 처리 오류: {item_error}")
                                    continue
                        
                        # 트랜잭션 커밋
                        await db.commit()
                        # After successful update, respond using freshly fetched charger statuses
                        cached_chargers = updated_chargers
                        print(f"✅ 충전기 정보 DB 저장 완료: {len(updated_chargers)}개 (fresh)")
        
        # === 4단계: 응답 데이터 구성 ===
        if not station_info:
            raise HTTPException(status_code=404, detail="충전소 정보를 찾을 수 없습니다.")
        
        # 제공 가능한 충전방식 추출
        available_charge_types = list(set([
            charger["charge_type"] for charger in cached_chargers 
            if charger["charge_type"]
        ]))
        
        # 각 충전기 정보 (상태코드 + 충전방식 매핑)
        charger_details = []
        for charger in cached_chargers:
            # 상태코드 해석 (KEPCO 기준)
            status_code = charger["status_code"]
            status_text = {
                "0": "사용가능",
                "1": "충전가능",
                "2": "충전중", 
                "3": "고장/점검",
                "4": "통신장애",
                "5": "통신미연결",
                "6": "예약중",
                "7": "운영중지",
                "8": "정비중",
                "9": "일시정지"
            }.get(status_code, f"알 수 없음({status_code})")
            
            charger_details.append({
                "charger_id": charger["charger_id"],
                "charger_name": charger["charger_name"],
                "status_code": status_code,
                "status_text": status_text,
                "charge_type": charger["charge_type"],
                # 추가 사용현황 정보
                "charge_type_description": {
                    "1": "완속 (AC 3상)",
                    "2": "급속 (DC차데모)",
                    "3": "급속 (DC콤보)",
                    "4": "완속 (AC단상)",
                    "5": "급속 (DC차데모+DC콤보)",
                    "6": "급속 (DC차데모+AC3상)",
                    "7": "급속 (DC콤보+AC3상)"
                }.get(charger["charge_type"], f"타입{charger['charge_type']}"),
                "last_updated": charger.get("stat_update_datetime", "정보없음"),
                "availability": "사용가능" if status_code in ["0", "1"] else "사용불가"
            })
        
        # === 5단계: Cache 저장 ===
        try:
            cache_key = f"station_detail:{station_id}"
            
            cache_data = {
                "station_info": _serialize_for_cache(station_info),
                "chargers": _serialize_for_cache(charger_details),
                "available_charge_types": available_charge_types,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            # use configured detail TTL (30 minutes by default)
            await redis_client.setex(cache_key, settings.CACHE_DETAIL_EXPIRE_SECONDS, json.dumps(_serialize_for_cache(cache_data), ensure_ascii=False))
            print(f"✅ 충전소 상세 정보 Cache 저장 완료")
        except Exception as cache_error:
            print(f"⚠️ Cache 저장 오류: {cache_error}")
        
        # Explicitly mark where the data came from so frontend can display/diagnose
        response_source = "api" if need_api_call else "database"

        return {
            "station_name": station_info["station_name"],
            "available_charge_types": ", ".join(available_charge_types),
            "charger_details": charger_details,
            "total_chargers": len(charger_details),
            "source": response_source,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"🚨 충전기 스펙 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
