import asyncio
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
# models.py에 정의된 Base 클래스를 임포트하여 중복 정의를 피함
from .models import Base
from .config import settings

# -----------------------------------------------------
# 비동기 DB 엔진 생성
# -----------------------------------------------------
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    future=True
)

# -----------------------------------------------------
# AsyncSession factory
# -----------------------------------------------------
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

# -----------------------------------------------------
# FastAPI 의존성용 세션 (DB 커넥션 관리)
# -----------------------------------------------------
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """
    DB 초기화: 모든 테이블을 생성합니다. (main.py에서 호출)
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
