import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from ..models import Base
from ..core.config import settings

# 🌟 [수정] settings.DATABASE_URL을 사용하여 비동기 드라이버(asyncpg)를 명시적으로 지정
# settings.DATABASE_URL에는 "postgresql://"로 시작하는 주소가 있으므로,
# 이를 "postgresql+asyncpg://"로 변경하여 비동기 연결을 강제합니다.
ASYNC_DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    ASYNC_DATABASE_URL, # 🌟 수정된 비동기 URL 사용
    echo=True,
    future=True
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # 세션 내에서 트랜잭션이 성공적으로 처리된 경우에만 커밋
            # 비동기 세션을 사용할 때는 commit() 호출이 필요합니다.
            await session.commit()
        except Exception:
            # 예외 발생 시 롤백
            await session.rollback()
            raise
        finally:
            # 세션 닫기
            await session.close()

# 데이터베이스에 테이블이 없는 경우 테이블을 생성하는 함수
async def init_db():
    async with engine.begin() as conn:
        # DB 연결 내에서 동기식으로 테이블 생성 명령을 실행
        await conn.run_sync(Base.metadata.create_all)
