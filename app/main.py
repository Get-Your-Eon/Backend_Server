from fastapi import FastAPI, Depends
import uvicorn
import redis.asyncio as redis
import json
from typing import Optional

# ----------------------------------------------------
# 실제 파일 경로에 맞게 상대 경로 임포트로 수정
# ----------------------------------------------------
from .config import settings
from .redis_client import init_redis_pool, get_redis_client


# FastAPI 인스턴스 생성 (변수 이름이 'app'이어야 합니다)
app = FastAPI(title="Codyssey Team A Backend API")

# ----------------------------------------------------
# FastAPI Startup 이벤트에 Redis 연결 설정
# ----------------------------------------------------
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 Redis 연결 풀을 초기화합니다."""
    print(f"Connecting to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}...")
    try:
        await init_redis_pool()
        print("Redis connection pool initialized successfully.")
    except Exception as e:
        print(f"CRITICAL: Failed to initialize Redis connection: {e}")
        # 실제 운영 환경에서는 서버 시작을 중단하는 로직을 추가할 수도 있습니다.


# ----------------------------------------------------
# 루트 엔드포인트 정의
# ----------------------------------------------------
@app.get("/")
def read_root():
    return {"message": "Server is running successfully!", "project": "Codyssey_Team_A"}


# ----------------------------------------------------
# Redis 연결 테스트 엔드포인트
# ----------------------------------------------------
@app.get("/redis-test")
async def redis_cache_test(
        redis_client: redis.Redis = Depends(get_redis_client)
):
    """
    Redis 연결을 테스트하고 데이터를 쓰고 읽습니다.
    """
    try:
        test_key = "app:status:check"
        test_value = {"status": "ok", "timestamp": "2025-10-05_21:30"}

        # Redis에 값 설정 (TTL 60초)
        await redis_client.set(test_key, json.dumps(test_value), ex=60)

        # Redis에서 값 가져오기
        cached_value = await redis_client.get(test_key)

        if cached_value:
            return {
                "message": "Redis connection test successful!",
                "data_stored": test_value,
                "data_retrieved": json.loads(cached_value)
            }
        else:
            return {"message": "Redis connection successful, but failed to retrieve data.", "status": "error"}

    except Exception as e:
        # 연결 실패 시 발생하는 예외 처리
        return {"message": "Redis operation FAILED!", "error": str(e), "status": "critical"}


if __name__ == "__main__":
    # 프로젝트를 실행하려면 터미널에서 다음 명령어를 사용해야 합니다.
    # uvicorn app.main:app --reload
    pass