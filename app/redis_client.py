# app/redis_client.py

import redis.asyncio as redis
from app.config import settings
from typing import Optional

# Redis 연결 풀을 관리할 전역 변수
redis_pool: Optional[redis.Redis] = None

# 1. Redis 연결 초기화 함수
async def init_redis_pool():
    """Redis 연결 풀을 생성하고 전역 변수에 할당합니다."""
    global redis_pool
    if redis_pool is None:
        redis_pool = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True # 데이터를 파이썬 문자열로 자동 디코딩
            # password=settings.REDIS_PASSWORD # 비밀번호가 있다면
        )

# 2. Redis 클라이언트 반환 의존성 함수 (FastAPI Depends 용)
async def get_redis_client() -> redis.Redis:
    """FastAPI 라우터에서 사용할 Redis 클라이언트 의존성 주입 함수입니다."""
    if redis_pool is None:
        await init_redis_pool() # 연결 풀이 초기화되지 않았다면 초기화
    return redis_pool