from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# 현재 프로젝트 설정을 임포트합니다.
from app.config import settings

# -----------------------------------------------------
# 비동기 데이터베이스 엔진 생성
# -----------------------------------------------------
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,             # 개발 환경에서 SQL 쿼리 로깅
    pool_recycle=3600      # 1시간마다 연결 재활용
)

# -----------------------------------------------------
# 세션 팩토리 설정
# -----------------------------------------------------
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# -----------------------------------------------------
# 모든 모델의 베이스 클래스 (Alembic 마이그레이션 및 모델 정의에 사용)
# -----------------------------------------------------
Base = declarative_base()

# -----------------------------------------------------
# 🚀 비동기 세션 의존성 (FastAPI 전용)
# -----------------------------------------------------
async def get_session() -> AsyncSession:
    """
    FastAPI의 Depends()에서 사용할 비동기 DB 세션 의존성 함수.
    요청이 완료되면 세션을 자동으로 종료합니다.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()   # 요청이 정상적으로 끝나면 커밋
        except Exception:
            await session.rollback() # 오류 발생 시 롤백
            raise
        finally:
            await session.close()    # 세션 종료

# main.py 등에서 사용할 alias
get_async_session = get_session
