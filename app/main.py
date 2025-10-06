import contextlib
import time
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text  # ✅ 추가: 문자열 SQL을 실행하기 위한 text() 함수
from redis.asyncio import Redis

# 프로젝트 내부 모듈 임포트
from app.config import settings
from app.database import get_async_session  # DB 세션 의존성
from app.redis_client import (
    init_redis_pool,
    close_redis_pool,
    get_redis_client,
    set_cache,
    get_cache
)
from app.api.v1.router import router as api_v1_router


# --- Lifespan Context Manager 정의 ---
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 서버 시작/종료 시 실행되는 이벤트 핸들러.
    DB 및 Redis 연결 초기화/종료 로직을 포함합니다.
    """
    print("Application startup: Initializing resources...")

    # 1. Redis 연결 풀 초기화
    await init_redis_pool()

    # [TODO] 2. DB 마이그레이션 확인 및 초기 데이터 로드 (필요시)
    # 현재는 init_db.py 스크립트로 별도 실행을 권장합니다.

    yield  # 서버가 실행되는 동안 유지

    print("Application shutdown: Cleaning up resources...")
    # 3. Redis 연결 풀 종료
    await close_redis_pool()


# --- FastAPI Application 인스턴스 생성 ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    description="Codyssey EV Charging Station API",
    lifespan=lifespan
)


# --- 기본 헬스 체크 엔드포인트 ---
@app.get("/", tags=["Infrastructure"])
def read_root():
    """기본 헬스 체크 엔드포인트"""
    return {
        "message": "Server is running successfully!",
        "project": settings.PROJECT_NAME,
        "api_version": settings.API_VERSION
    }


# --- V1 API 라우터 포함 ---
app.include_router(api_v1_router, prefix="/api/v1")


# --- DB 연결 테스트 엔드포인트 ---
@app.get("/db-test", tags=["Infrastructure"], summary="데이터베이스 연결 및 쿼리 테스트")
async def db_test_endpoint(db: AsyncSession = Depends(get_async_session)):
    """
    DB 연결 상태 및 간단한 쿼리 실행 가능 여부를 테스트합니다.
    """
    start_time = time.time()
    try:
        # ✅ SQLAlchemy의 text()를 사용해야 함
        result = await db.execute(text("SELECT 1"))
        if result.scalar_one():
            response_time_ms = (time.time() - start_time) * 1000
            return {
                "message": "Database connection test successful!",
                "status": "ok",
                "response_time_ms": f"{response_time_ms:.2f}"
            }
        else:
            raise Exception("SQL query did not return expected result.")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {e.__class__.__name__}: {e}"
        )


# --- Redis 연결 테스트 엔드포인트 ---
@app.get("/redis-test", tags=["Infrastructure"], summary="Redis 캐시 연결 테스트")
async def redis_test_endpoint(redis_client: Redis = Depends(get_redis_client)):
    """
    Redis 서버에 데이터를 쓰고 읽는 테스트를 수행합니다.
    """
    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis client is not initialized or connected."
        )

    test_key = "infra:test:key"
    test_data = {
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    }

    try:
        # 1. 쓰기 테스트
        await set_cache(test_key, test_data, expire=10)

        # 2. 읽기 테스트
        retrieved_data = await get_cache(test_key)

        if retrieved_data and retrieved_data["status"] == "ok":
            return {
                "message": "Redis connection test successful!",
                "data_stored": test_data,
                "data_retrieved": retrieved_data,
                "status": "ok"
            }
        else:
            raise Exception("Data mismatch or failed to retrieve.")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redis operation FAILED!: {e.__class__.__name__}: {e}"
        )
