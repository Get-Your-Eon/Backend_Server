import os
import sys
import asyncio
from dotenv import load_dotenv
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import pool
from alembic import context

# ----------------------------------------------------
# 1. 환경 설정 및 모델 임포트
# ----------------------------------------------------

# .env 파일 로드
load_dotenv()

# 프로젝트 루트 경로를 시스템 경로에 추가
sys.path.append(os.getcwd())

# Base 모델 임포트
from app.models import Base  # app.models 임포트는 유지

# Alembic Config 객체
config = context.config

# 로깅 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ----------------------------------------------------
# 2. 메타데이터 설정
# ----------------------------------------------------
target_metadata = Base.metadata

# ----------------------------------------------------
# 3. 오프라인 마이그레이션
# ----------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

# ----------------------------------------------------
# 4. 마이그레이션 실행 (동기)
# ----------------------------------------------------
def do_run_migrations(connection):
    """동기식으로 Alembic 마이그레이션 실행"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )
    with context.begin_transaction():
        context.run_migrations()

# ----------------------------------------------------
# 5. 비동기 마이그레이션
# ----------------------------------------------------
async def run_async_migrations(connectable):
    """비동기 마이그레이션 실행 헬퍼"""
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

async def run_migrations_online_async():
    """비동기 DB 엔진을 생성하고 마이그레이션 실행"""
    from app.config import settings

    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql://"):
        async_db_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        async_db_url = database_url

    print(f"[DEBUG] ASYNC_DATABASE_URL being used: {async_db_url}")

    connectable = create_async_engine(
        async_db_url,
        poolclass=pool.NullPool,
    )

    async with connectable.begin() as conn:
        await conn.run_sync(do_run_migrations)

    await connectable.dispose()

# ----------------------------------------------------
# 6. 온라인(비동기) 실행 래퍼
# ----------------------------------------------------
def run_migrations_online() -> None:
    """Run migrations in 'online' (async) mode."""
    asyncio.run(run_migrations_online_async())

# ----------------------------------------------------
# 7. 실행 진입점
# ----------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
