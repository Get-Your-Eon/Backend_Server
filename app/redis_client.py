import json
from typing import Any, Optional
from redis.asyncio import Redis
from .core.config import settings

redis_pool: Optional[Redis] = None

async def init_redis_pool():
    """
    Redis 연결 초기화
    - settings에서 자동으로 선택된 호스트/포트/비밀번호 사용
    - 연결 성공/실패 로그 출력
    """
    global redis_pool
    try:
        redis_pool = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )
        await redis_pool.ping()
        print(f"✅ Redis connected ({settings.REDIS_HOST}:{settings.REDIS_PORT})")
    except Exception as e:
        print(f"❌ Redis connection failed ({settings.REDIS_HOST}:{settings.REDIS_PORT}): {e}")
        redis_pool = None

async def close_redis_pool():
    """
    Redis 연결 종료
    """
    global redis_pool
    if redis_pool:
        await redis_pool.close()
        redis_pool = None

async def get_redis_client() -> Optional[Redis]:
    """
    현재 Redis 클라이언트 반환
    """
    return redis_pool

async def get_cache(key: str, client: Optional[Redis] = None) -> Any:
    """
    캐시 조회
    """
    current_client = client or redis_pool
    if current_client is None:
        return None
    data = await current_client.get(key)
    return json.loads(data) if data else None

async def set_cache(
        key: str,
        value: Any,
        expire: int = settings.CACHE_EXPIRE_SECONDS,
        client: Optional[Redis] = None
):
    """
    캐시 저장
    """
    current_client = client or redis_pool
    if current_client is None:
        return
    await current_client.set(key, json.dumps(value, default=str), ex=expire)

async def delete_cache(key: str, client: Optional[Redis] = None):
    """
    캐시 삭제
    """
    current_client = client or redis_pool
    if current_client:
        await current_client.delete(key)
