from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings

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
# FastAPI 의존성용 세션
# -----------------------------------------------------
async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
