import contextlib
import time
from datetime import datetime
import os

from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, Response, Header
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

# --- V1 API 라우터 포함 (일반 사용자 접근 가능) ---
app.include_router(api_router, prefix="/api/v1")

# --- 관리자 전용 엔드포인트 ---
admin_router = APIRouter(dependencies=[Depends(admin_required)])

@admin_router.get("/admin-only-data")
async def admin_data():
    return {"msg": "관리자 전용 데이터입니다."}

app.include_router(admin_router, prefix="/admin")


# Temporary endpoint: allow frontend API key holders to delete station detail cache keys
@app.post("/admin/cache-unlocked")
async def delete_station_cache_unlocked(payload: dict = Body(...), _ok: bool = Depends(frontend_api_key_required)):
    key = payload.get("key")
    if not key or not key.startswith("station:detail:"):
        raise HTTPException(status_code=400, detail="Only station detail keys are allowed")
    redis_client = await get_redis_client()
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis not available")
    try:
        deleted = await redis_client.delete(key)
        return {"deleted": bool(deleted), "key": key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
