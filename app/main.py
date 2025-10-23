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
import httpx
import math

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
@app.get("/api/v1/stations", tags=["Station"], summary="Search EV charging stations and chargers")
async def search_ev_stations(
    lat: float = Query(..., description="Latitude coordinate (required from frontend)"),
    lon: float = Query(..., description="Longitude coordinate (required from frontend)"), 
    radius: int = Query(..., description="Search radius in meters (required from frontend)", ge=100, le=10000),
    page: int = Query(1, description="Page number", ge=1),
    limit: int = Query(20, description="Results per page", ge=1, le=100),
    _: bool = Depends(frontend_api_key_required),
    db: AsyncSession = Depends(get_async_session),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    EV 충전소/충전기 검색 API (보조금 조회와 완전 분리)
    
    프론트엔드 요청: 위도, 경도, 반경(meter)
    백엔드 응답: KEPCO API 데이터 전달
    
    3단계 캐싱 전략:
    1. Redis 캐시 조회 → 있으면 바로 반환
    2. DB 정적 데이터 조회 → 있으면 캐시 저장 후 반환  
    3. KEPCO API 호출 → DB & 캐시 저장 후 반환
    
    반경 기준값: 500, 1000, 3000, 5000, 10000 (요청값을 올림)
    """
    try:
        from app.core.config import settings
        from app.redis_client import get_cache, set_cache
        
        # === 헬퍼 함수들 ===
        def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            """거리 계산 (하버사인 공식)"""
            R = 6371000  # 지구 반지름(미터)
            lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
            delta_lat, delta_lon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
            
            a = (math.sin(delta_lat/2)**2 + 
                 math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c

        async def coordinates_to_address(lat: float, lon: float) -> str:
            """위도/경도 → 한국 주소 변환 (KEPCO API addr 파라미터용)"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://nominatim.openstreetmap.org/reverse",
                        params={
                            "format": "json",
                            "lat": lat,
                            "lon": lon,
                            "accept-language": "ko",
                            "addressdetails": 1
                        },
                        headers={"User-Agent": "EV-Station-Search/1.0"},
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        addr = data.get("address", {})
                        
                        # 한국 주소 형식으로 조합
                        parts = []
                        for key in ["state", "city", "county", "district", "neighbourhood"]:
                            if addr.get(key):
                                parts.append(addr[key])
                        
                        if parts:
                            return " ".join(parts)
            except:
                pass
            
            return "서울특별시 강남구"  # 기본값

        # === 1. 반경 기준값 매핑 ===
        radius_levels = [500, 1000, 3000, 5000, 10000]
        mapped_radius = next((r for r in radius_levels if radius <= r), 10000)
        
        # === 2. 좌표 → 주소 변환 ===
        search_addr = await coordinates_to_address(lat, lon)
        
        # === 3. 캐시 키 생성 ===
        cache_key = f"ev_stations:{search_addr}:{mapped_radius}:v2"
        
        # === 4. [1단계] 캐시 조회 ===
        cached = await get_cache(cache_key)
        if cached and "stations" in cached:
            return {
                "message": "충전소 데이터 (캐시에서 조회)",
                "status": "cache_hit",
                "count": len(cached["stations"]),
                "stations": cached["stations"][:limit],
                "source": "redis_cache",
                "search_addr": search_addr,
                "mapped_radius": mapped_radius
            }
        
        # === 5. [2단계] DB 정적 데이터 조회 ===
        static_query = text("""
            SELECT DISTINCT
                COALESCE(cs_id, id::text) as station_id,
                COALESCE(cs_nm, name) as station_name,
                COALESCE(addr, address) as station_address,
                COALESCE(lat::float, ST_Y(location::geometry)) as latitude,
                COALESCE(longi::float, ST_X(location::geometry)) as longitude
            FROM stations 
            WHERE (addr ILIKE :search_pattern OR address ILIKE :search_pattern)
                AND (lat IS NOT NULL AND longi IS NOT NULL)
            ORDER BY station_id
            LIMIT 50
        """)
        
        db_result = await db.execute(static_query, {
            "search_pattern": f"%{search_addr.split()[0]}%"
        })
        
        static_stations = []
        for row in db_result.fetchall():
            r = row._mapping
            try:
                distance = calculate_distance(lat, lon, r["latitude"], r["longitude"])
                if distance <= mapped_radius:
                    static_stations.append({
                        "station_id": r["station_id"],
                        "station_name": r["station_name"],
                        "address": r["station_address"],
                        "lat": r["latitude"],
                        "lon": r["longitude"],
                        "distance_m": int(distance)
                    })
            except:
                continue
        
        if static_stations:
            static_stations.sort(key=lambda x: x["distance_m"])
            cache_data = {"stations": static_stations}
            await set_cache(cache_key, cache_data, expire=300)  # 5분
            
            return {
                "message": "충전소 데이터 (DB 정적 데이터)",
                "status": "db_static",
                "count": len(static_stations),
                "stations": static_stations[:limit],
                "source": "database",
                "search_addr": search_addr,
                "mapped_radius": mapped_radius
            }
        
        # === 6. [3단계] KEPCO API 실시간 호출 ===
        kepco_url = settings.EXTERNAL_STATION_API_BASE_URL
        kepco_key = settings.EXTERNAL_STATION_API_KEY
        
        if not kepco_url or not kepco_key:
            raise HTTPException(
                status_code=500,
                detail="KEPCO API 설정 누락"
            )
        
        # API 문서 정확한 구현: GET 요청, 쿼리 파라미터
        async with httpx.AsyncClient() as client:
            kepco_response = await client.get(
                kepco_url,
                params={
                    "addr": search_addr,           # 선택 파라미터
                    "apiKey": kepco_key,           # 필수 파라미터 (40자리)
                    "returnType": "json"           # 선택 파라미터
                },
                timeout=30.0
            )
            
            if kepco_response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"KEPCO API 오류: HTTP {kepco_response.status_code}"
                )
            
            kepco_json = kepco_response.json()
        
        # === 7. KEPCO 응답 데이터 처리 ===
        stations_list = []
        if "data" in kepco_json and isinstance(kepco_json["data"], list):
            for item in kepco_json["data"]:
                try:
                    # API 문서 필드명 정확히 매핑
                    station_lat = float(item.get("lat", 0))
                    station_lon = float(item.get("longi", 0))
                    
                    if station_lat == 0 or station_lon == 0:
                        continue
                    
                    # 거리 필터링
                    distance = calculate_distance(lat, lon, station_lat, station_lon)
                    if distance > mapped_radius:
                        continue
                    
                    # 응답 데이터 구성 (API 문서 필드명 사용)
                    processed_station = {
                        "station_id": item.get("csId", ""),        # 충전소ID
                        "station_name": item.get("csNm", ""),      # 충전소명칭
                        "address": item.get("addr", ""),           # 충전기주소
                        "lat": station_lat,                        # 위도
                        "lon": station_lon,                        # 경도
                        "distance_m": int(distance),
                        # 충전기 세부 정보
                        "charger_id": item.get("cpId", ""),        # 충전기ID
                        "charger_name": item.get("cpNm", ""),      # 충전기명칭
                        "charger_status": item.get("cpStat", ""),  # 상태코드 (1:충전가능, 2:충전중, ...)
                        "charge_type": item.get("chargeTp", ""),   # 충전기타입 (1:완속, 2:급속)
                        "connector_type": item.get("cpTp", ""),    # 충전방식 (1:B타입, 2:C타입, ...)
                        "last_updated": item.get("statUpdateDatetime", "")  # 상태갱신시각
                    }
                    stations_list.append(processed_station)
                    
                    # === 8. DB 저장 (정적 + 동적 데이터) ===
                    # 충전소 테이블 upsert
                    station_upsert = text("""
                        INSERT INTO stations (cs_id, cs_nm, addr, lat, longi, location, updated_at)
                        VALUES (:cs_id, :cs_nm, :addr, :lat, :longi, 
                                ST_SetSRID(ST_MakePoint(:longi, :lat), 4326), NOW())
                        ON CONFLICT (cs_id) DO UPDATE SET
                            cs_nm = EXCLUDED.cs_nm,
                            addr = EXCLUDED.addr,
                            lat = EXCLUDED.lat,
                            longi = EXCLUDED.longi,
                            location = EXCLUDED.location,
                            updated_at = NOW()
                    """)
                    
                    await db.execute(station_upsert, {
                        "cs_id": item.get("csId"),
                        "cs_nm": item.get("csNm"),
                        "addr": item.get("addr"),
                        "lat": str(station_lat),
                        "longi": str(station_lon)
                    })
                    
                    # 충전기 테이블 upsert
                    charger_upsert = text("""
                        INSERT INTO chargers (cp_id, cp_nm, cp_stat, charge_tp, cp_tp, 
                                            kepco_stat_update_datetime, cs_id, updated_at)
                        VALUES (:cp_id, :cp_nm, :cp_stat, :charge_tp, :cp_tp, 
                                :stat_time, :cs_id, NOW())
                        ON CONFLICT (cp_id) DO UPDATE SET
                            cp_nm = EXCLUDED.cp_nm,
                            cp_stat = EXCLUDED.cp_stat,
                            charge_tp = EXCLUDED.charge_tp,
                            cp_tp = EXCLUDED.cp_tp,
                            kepco_stat_update_datetime = EXCLUDED.kepco_stat_update_datetime,
                            updated_at = NOW()
                    """)
                    
                    await db.execute(charger_upsert, {
                        "cp_id": item.get("cpId"),
                        "cp_nm": item.get("cpNm"),
                        "cp_stat": item.get("cpStat"),
                        "charge_tp": item.get("chargeTp"),
                        "cp_tp": item.get("cpTp"),
                        "stat_time": item.get("statUpdateDatetime"),
                        "cs_id": item.get("csId")
                    })
                    
                except (ValueError, TypeError):
                    continue
            
            # DB 커밋
            await db.commit()
        
        # === 9. 최종 결과 정리 및 캐시 저장 ===
        stations_list.sort(key=lambda x: x["distance_m"])
        final_result = stations_list[:limit]
        
        # 30분 캐시 저장
        cache_data = {"stations": stations_list}
        await set_cache(cache_key, cache_data, expire=1800)
        
        return {
            "message": "충전소 데이터 (KEPCO API 실시간 조회)",
            "status": "kepco_api_success",
            "count": len(final_result),
            "stations": final_result,
            "source": "kepco_realtime",
            "search_addr": search_addr,
            "mapped_radius": mapped_radius,
            "total_found": len(stations_list)
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
