import json
from typing import Any, Optional
# redis.asyncio as redis 대신, Redis 클래스를 명시적으로 임포트하여 사용합니다.
from redis.asyncio import Redis
from .config import settings

# redis_pool 변수의 타입을 명시적으로 Redis 인스턴스 또는 None으로 지정
redis_pool: Optional[Redis] = None

async def init_redis_pool():
    global redis_pool
    try:
        # Redis 클래스를 사용하여 클라이언트 인스턴스 생성
        # config.py에 정의된 REDIS_PASSWORD를 사용하여 연결합니다. (비밀번호가 비어있지 않은 경우)
        redis_pool = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,
            # REDIS_PASSWORD가 설정되어 있으면 사용하고, 없으면 None을 전달합니다.
            password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            decode_responses=True,
        )
        await redis_pool.ping()
        print(f"✅ Redis connection successful ({settings.REDIS_HOST}:{settings.REDIS_PORT})")
    except Exception as e:
        print(f"❌ Redis connection failed ({settings.REDIS_HOST}:{settings.REDIS_PORT}): {e}")
        redis_pool = None

async def close_redis_pool():
    global redis_pool
    if redis_pool:
        await redis_pool.close()
        redis_pool = None

async def get_redis_client() -> Optional[Redis]:
    return redis_pool

# get_cache 함수에 옵션 인수인 client를 추가하여 2개 인수로 호출되어도 오류가 나지 않도록 수정
async def get_cache(key: str, client: Optional[Redis] = None) -> Any:
    # client가 제공되지 않으면 전역 redis_pool을 사용
    current_client: Optional[Redis] = client if client is not None else redis_pool

    # 클라이언트 인스턴스가 None인 경우 즉시 None 반환 (None.get() 오류 방지)
    if current_client is None:
        return None

    # 클라이언트 인스턴스에서 get 메서드를 명시적으로 호출
    data = await current_client.get(key)
    return json.loads(data) if data else None

# set_cache 함수에도 옵션 인수인 client를 추가하여 유연성을 확보
async def set_cache(key: str, value: Any, expire: int = settings.CACHE_EXPIRE_SECONDS, client: Optional[Redis] = None):
    # client가 제공되지 않으면 전역 redis_pool을 사용
    current_client: Optional[Redis] = client if client is not None else redis_pool

    # 클라이언트 인스턴스가 None인 경우 즉시 종료 (None.set() 오류 방지)
    if current_client is None:
        return

    # default=str을 사용하여 datetime 객체 등을 직렬화할 때 발생하는 오류 방지
    # 클라이언트 인스턴스에서 set 메서드를 명시적으로 호출
    await current_client.set(key, json.dumps(value, default=str), ex=expire)

async def delete_cache(key: str):
    if redis_pool:
        await redis_pool.delete(key)
