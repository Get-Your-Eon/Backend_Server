import contextlib
import time
from datetime import datetime
import os

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from redis.asyncio import Redis

# 프로젝트 내부 모듈 임포트
from app.core.config import settings    # type: ignore
from app.db.database import get_async_session # type: ignore
from app.redis_client import (  # type: ignore
    init_redis_pool,    # type: ignore
    close_redis_pool,   # type: ignore
    get_redis_client,   # type: ignore
    set_cache,  # type: ignore
    get_cache   # type: ignore
)
from app.api.v1.api import api_router   # type: ignore

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

# --- HTTP Basic 인증 (관리자 전용, 다중 계정 지원) ---
security = HTTPBasic()
raw_admins = os.getenv("ADMIN_CREDENTIALS", "")
ADMIN_ACCOUNTS = dict([cred.split(":") for cred in raw_admins.split(",") if cred])

def admin_required(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username not in ADMIN_ACCOUNTS or ADMIN_ACCOUNTS[credentials.username] != credentials.password:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# --- FastAPI Application 생성 ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    description="Codyssey EV Charging Station API",
    lifespan=lifespan,
    docs_url=None,    # docs URL을 직접 라우트로 재정의
    redoc_url=None,
    openapi_url="/openapi.json" if IS_ADMIN else None
)

# --- 관리자용 docs & redoc 엔드포인트 ---
if IS_ADMIN:
    from fastapi import APIRouter

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

# --- V1 API 라우터 포함 (일반 사용자 접근 가능) ---
app.include_router(api_router, prefix="/api/v1")

# --- 관리자 전용 엔드포인트 ---
admin_router = APIRouter(dependencies=[Depends(admin_required)])

@admin_router.get("/admin-only-data")
async def admin_data():
    return {"msg": "관리자 전용 데이터입니다."}

app.include_router(admin_router, prefix="/admin")

# --- DB 연결 테스트 엔드포인트 ---
@app.get("/db-test", tags=["Infrastructure"], summary="DB 연결 및 쿼리 테스트")
async def db_test_endpoint(test_value: str = "1", db: AsyncSession = Depends(get_async_session)):
    """
    test_value를 받아서 SELECT 쿼리 실행
    예: /db-test?test_value=123
    """
    start_time = time.time()
    try:
        # 문자열로 바인딩 쿼리
        result = await db.execute(text("SELECT :val"), {"val": test_value})
        scalar_result = result.scalar_one()
        response_time_ms = (time.time() - start_time) * 1000
        return {
            "message": "Database connection test successful!",
            "status": "ok",
            "test_value": test_value,
            "db_result": scalar_result,
            "response_time_ms": f"{response_time_ms:.2f}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {e.__class__.__name__}: {e}"
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
