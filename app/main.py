import contextlib
import time
from datetime import datetime
import os

from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, Response, Header, Body, Query
from typing import Optional
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from redis.asyncio import Redis

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
from fastapi import Body
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_async_session

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

# --- 충전소 검색 엔드포인트 (보조금 기능과 독립) ---
@app.get("/api/v1/stations", tags=["Station"], summary="Search charging stations by location")
async def search_stations_direct(
    lat: float = Query(..., description="Latitude coordinate (required)"),
    lon: float = Query(..., description="Longitude coordinate (required)"), 
    radius: int = Query(..., description="Search radius in meters (required)", ge=100, le=10000),
    page: int = Query(1, description="Page number", ge=1),
    limit: int = Query(20, description="Results per page", ge=1, le=100),
    _: bool = Depends(frontend_api_key_required),
    db: AsyncSession = Depends(get_async_session),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    Search for EV charging stations within specified radius.
    
    3-tier caching strategy:
    1. Cache lookup → return if found
    2. DB lookup (static data only) → return if found 
    3. KEPCO API call → save to DB & cache → return
    
    Required parameters:
    - lat: Latitude coordinate (프론트엔드에서 필수 제공)
    - lon: Longitude coordinate (프론트엔드에서 필수 제공) 
    - radius: Search radius in meters (프론트엔드에서 필수 제공)
    - x-api-key: API key in header
    """
    try:
        import httpx
        import math
        from app.core.config import settings
        from app.redis_client import get_cache, set_cache
        
        # 헬퍼 함수 정의
        def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            """두 지점 간의 거리를 미터 단위로 계산"""
            R = 6371000  # 지구 반지름 (미터)
            lat1_rad = math.radians(lat1)
            lat2_rad = math.radians(lat2)
            delta_lat = math.radians(lat2 - lat1)
            delta_lon = math.radians(lon2 - lon1)
            
            a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) +
                 math.cos(lat1_rad) * math.cos(lat2_rad) *
                 math.sin(delta_lon/2) * math.sin(delta_lon/2))
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c
        
        # 1. 반경 기준값 매핑 (요청값을 기준값으로 올림)
        radius_thresholds = [500, 1000, 3000, 5000, 10000]
        actual_radius = next((r for r in radius_thresholds if radius <= r), 10000)
        
        # 2. 위도/경도를 주소(addr)로 변환
        async def get_address_from_coords(lat: float, lon: float) -> str:
            """위도/경도를 시/군/구/동 주소로 변환"""
            try:
                # Nominatim (OpenStreetMap) 역지오코딩 사용
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://nominatim.openstreetmap.org/reverse",
                        params={
                            "format": "json",
                            "lat": lat,
                            "lon": lon,
                            "accept-language": "ko"
                        },
                        headers={"User-Agent": "EV-Charger-Search/1.0"},
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        address_parts = data.get("address", {})
                        
                        # 시/군/구/동 조합
                        city = address_parts.get("city", "")
                        county = address_parts.get("county", "")
                        district = address_parts.get("district", "")
                        neighbourhood = address_parts.get("neighbourhood", "")
                        
                        addr_parts = [p for p in [city, county, district, neighbourhood] if p]
                        return " ".join(addr_parts) if addr_parts else "서울특별시 강남구"
                    
            except Exception:
                pass
            
            # 기본값 (지오코딩 실패 시)
            return "서울특별시 강남구"
        
        addr = await get_address_from_coords(lat, lon)
        
        # 3. 캐시 키 생성
        cache_key = f"stations:{addr}:{actual_radius}"
        
        # 4. (1단계) 캐시 조회
        cached_data = await get_cache(cache_key)
        if cached_data:
            return {
                "message": "Data from cache",
                "status": "cache_hit",
                "count": len(cached_data.get("stations", [])),
                "stations": cached_data.get("stations", []),
                "source": "cache",
                "addr": addr,
                "actual_radius": actual_radius
            }
        
        # 5. (2단계) DB 조회 (정적 데이터만)
        db_query = text("""
            SELECT 
                COALESCE(cs_id, id::text) as id,
                COALESCE(cs_nm, name) as name,
                COALESCE(addr, address) as address,
                COALESCE(lat::float, ST_Y(location::geometry)) as lat,
                COALESCE(longi::float, ST_X(location::geometry)) as lon,
                (SELECT COUNT(1) FROM chargers c WHERE c.station_id = stations.id) as charger_count
            FROM stations 
            WHERE (addr ILIKE :addr OR address ILIKE :addr_pattern)
            ORDER BY id
            LIMIT :limit
        """)
        
        db_result = await db.execute(db_query, {
            "addr": f"%{addr}%",
            "addr_pattern": f"%{addr.split()[0]}%",  # 첫 번째 지역명으로도 검색
            "limit": limit * 2  # 충분한 데이터 확보
        })
        
        db_stations = []
        for row in db_result.fetchall():
            r = row._mapping
            if r["lat"] and r["lon"]:
                # 거리 계산
                distance = calculate_distance(lat, lon, float(r["lat"]), float(r["lon"]))
                if distance <= actual_radius:
                    db_stations.append({
                        "id": r["id"],
                        "name": r["name"],
                        "address": r["address"],
                        "lat": float(r["lat"]),
                        "lon": float(r["lon"]),
                        "distance_m": int(distance),
                        "charger_count": r["charger_count"]
                    })
        
        if db_stations:
            # DB에서 찾은 경우 캐시에 저장하고 반환
            db_stations.sort(key=lambda x: x["distance_m"])
            result_data = {
                "stations": db_stations[:limit]
            }
            await set_cache(cache_key, result_data, expire=300)  # 5분 캐시
            
            return {
                "message": "Data from database (static)",
                "status": "db_hit",
                "count": len(result_data["stations"]),
                "stations": result_data["stations"],
                "source": "database",
                "addr": addr,
                "actual_radius": actual_radius
            }
        
        # 6. (3단계) KEPCO API 호출
        kepco_url = settings.EXTERNAL_STATION_API_BASE_URL
        kepco_api_key = settings.EXTERNAL_STATION_API_KEY
        
        if not kepco_url or not kepco_api_key:
            raise HTTPException(status_code=500, detail="KEPCO API configuration missing")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                kepco_url,
                json={
                    "addr": addr,
                    "api_key": kepco_api_key,
                    "returnType": "json"
                },
                headers={"Content-Type": "application/json"},
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail=f"KEPCO API error: {response.status_code}")
            
            kepco_data = response.json()
            
            # 7. KEPCO 데이터 처리 및 DB 저장
            api_stations = []
            if "data" in kepco_data and kepco_data["data"]:
                for item in kepco_data["data"]:
                    try:
                        item_lat = float(item.get("lat", 0))
                        item_lon = float(item.get("longi", 0))
                        
                        if item_lat == 0 or item_lon == 0:
                            continue
                        
                        distance = calculate_distance(lat, lon, item_lat, item_lon)
                        
                        if distance <= actual_radius:
                            station_data = {
                                "id": item.get("csId", ""),
                                "name": item.get("csNm", ""),
                                "address": item.get("addr", ""),
                                "lat": item_lat,
                                "lon": item_lon,
                                "distance_m": int(distance),
                                "charger_count": 1
                            }
                            api_stations.append(station_data)
                            
                            # DB에 저장 (upsert)
                            upsert_query = text("""
                                INSERT INTO stations (cs_id, cs_nm, addr, lat, longi, location, created_at, updated_at)
                                VALUES (:cs_id, :cs_nm, :addr, :lat, :longi, 
                                        ST_SetSRID(ST_MakePoint(:longi, :lat), 4326), NOW(), NOW())
                                ON CONFLICT (cs_id) DO UPDATE SET
                                    cs_nm = EXCLUDED.cs_nm,
                                    addr = EXCLUDED.addr,
                                    lat = EXCLUDED.lat,
                                    longi = EXCLUDED.longi,
                                    location = EXCLUDED.location,
                                    updated_at = NOW()
                            """)
                            
                            await db.execute(upsert_query, {
                                "cs_id": item.get("csId"),
                                "cs_nm": item.get("csNm"),
                                "addr": item.get("addr"),
                                "lat": str(item_lat),
                                "longi": str(item_lon)
                            })
                            
                    except (ValueError, TypeError, Exception):
                        continue
                
                await db.commit()
            
            # 8. 결과 정렬 및 캐시 저장
            api_stations.sort(key=lambda x: x["distance_m"])
            final_stations = api_stations[:limit]
            
            result_data = {"stations": final_stations}
            await set_cache(cache_key, result_data, expire=1800)  # 30분 캐시
            
            return {
                "message": "Data from KEPCO API (saved to DB & cache)",
                "status": "api_call",
                "count": len(final_stations),
                "stations": final_stations,
                "source": "kepco_api",
                "addr": addr,
                "actual_radius": actual_radius
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {str(e)}"
        )

# --- V1 API 라우터 포함 (일반 사용자 접근 가능) ---
app.include_router(api_router, prefix="/api/v1")

# --- 관리자 전용 엔드포인트 ---
admin_router = APIRouter(dependencies=[Depends(admin_required)])

@admin_router.get("/admin-only-data")
async def admin_data():
    return {"msg": "관리자 전용 데이터입니다."}

app.include_router(admin_router, prefix="/admin")




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
    test_data = {"status": "ok", "timestamp": datetime.now().isoformat()}
    try:
        await set_cache(test_key, test_data, expire=10)
        retrieved_data = await get_cache(test_key)
        if retrieved_data and retrieved_data["status"] == "ok":
            return {"message": "Redis connection test successful!", "data_stored": test_data, "data_retrieved": retrieved_data, "status": "ok"}
        else:
            raise Exception("Data mismatch or retrieval failed.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Redis operation FAILED!: {e.__class__.__name__}: {e}")
