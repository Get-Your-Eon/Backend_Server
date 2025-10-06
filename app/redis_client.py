import redis.asyncio as redis
import json
import contextlib
from typing import Any, Optional, AsyncGenerator
from .config import settings

# Redis 클라이언트 인스턴스 (연결 풀 역할)
# NOTE: redis.asyncio.Redis 인스턴스가 연결 풀 역할을 수행합니다.
redis_pool: Optional[redis.Redis] = None

async def init_redis_pool():
    """Redis 연결 풀을 초기화하고 전역 redis_pool 변수에 할당합니다."""
    global redis_pool
    try:
        # decode_responses=True는 Redis에서 읽은 값을 문자열로 자동 변환합니다.
        # connection_pool은 내부적으로 관리됩니다.
        redis_pool = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,
            decode_responses=True,
            # max_connections 등을 설정하여 풀 크기를 제어할 수 있습니다.
        )
        # 풀이 제대로 초기화되었는지 확인하기 위해 ping을 실행합니다.
        await redis_pool.ping()
        print("Redis connection successful.")
    except Exception as e:
        print(f"Redis connection failed: {e}")
        # 연결 실패 시에도 애플리케이션 실행을 위해 None으로 유지
        redis_pool = None

async def close_redis_pool():
    """Redis 연결 풀을 종료합니다. (app.main의 lifespan 종료 로직에서 호출됨)"""
    global redis_pool
    if redis_pool:
        # redis.asyncio의 close()는 내부적으로 모든 연결을 닫고 풀을 정리합니다.
        await redis_pool.close()
        redis_pool = None

# [핵심 수정 완료]: @asynccontextmanager를 제거하고 클라이언트 인스턴스 자체를 반환하도록 수정
async def get_redis_client() -> Optional[redis.Redis]:
    """
    FastAPI의 Depends에서 사용하기 위한 의존성 주입 함수입니다.
    Redis 풀(redis_pool) 인스턴스를 직접 반환합니다.
    """
    return redis_pool

# --- 기존 캐시 유틸리티 함수들도 redis_pool을 사용하도록 수정 ---

async def get_cache(key: str) -> Optional[Any]:
    """
    Redis에서 캐시를 조회하고, JSON 문자열을 파이썬 객체로 변환합니다.
    """
    if not redis_pool:
        return None

    cached_data = await redis_pool.get(key)
    if cached_data:
        # JSON 문자열을 다시 파이썬 객체로 역직렬화
        return json.loads(cached_data)
    return None

async def set_cache(key: str, value: Any, expire: int = settings.CACHE_EXPIRE_SECONDS):
    """
    Redis에 값을 저장하고, 파이썬 객체를 JSON 문자열로 변환하여 저장합니다.
    """
    if not redis_pool:
        return

    # 파이썬 객체를 JSON 문자열로 직렬화
    serialized_value = json.dumps(value, default=str)
    await redis_pool.set(key, serialized_value, ex=expire)

async def delete_cache(key: str):
    """Redis에서 특정 키의 캐시를 삭제합니다."""
    if redis_pool:
        await redis_pool.delete(key)
