import os
import sys
import asyncio
from dotenv import load_dotenv
from logging.config import fileConfig

# 동기 엔진 임포트 (마이그레이션이 동기 접속을 선호하므로 추가)
from sqlalchemy import create_engine, pool
from alembic import context

# ----------------------------------------------------
# 1. 환경 설정 및 모델 임포트
# ----------------------------------------------------

# .env.production 파일 로드 (config에서 이미 했지만, alembic 단독 실행을 위해 유지)
load_dotenv()

# 프로젝트 루트 경로를 시스템 경로에 추가
sys.path.append(os.getcwd())

# Base 모델 임포트: 구조 분석 결과, Base는 app.models에 있습니다.
from app.models import Base

# settings 객체 임포트: app.core.config에서 가져옵니다.
from app.core.config import settings

# Alembic Config 객체
config = context.config

# 로깅 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ----------------------------------------------------
# 🌟 A. 동기 접속 URL 설정 (핵심 수정 부분)
# ----------------------------------------------------
db_url_from_ini = config.get_main_option("sqlalchemy.url")

# settings.DATABASE_URL을 사용하여 Render DB URL을 직접 설정합니다.
if db_url_from_ini is None:
    # 🌟 [수정] settings에서 직접 DATABASE_URL을 가져와 사용
    db_url_from_ini = settings.DATABASE_URL

# asyncpg 드라이버를 동기 드라이버로 변경합니다. (postgresql+asyncpg:// -> postgresql://)
# Alembic은 동기 접속을 사용해야 합니다.
if db_url_from_ini and db_url_from_ini.startswith("postgresql+asyncpg://"):
    db_url_from_ini = db_url_from_ini.replace("postgresql+asyncpg://", "postgresql://", 1)

if db_url_from_ini:
    # 혹시 모를 공백을 제거하고 sqlalchemy.url로 설정
    config.set_main_option("sqlalchemy.url", db_url_from_ini.strip())


# ----------------------------------------------------
# 2. 메타데이터 설정 (기존 유지)
# ----------------------------------------------------
target_metadata = Base.metadata

# ----------------------------------------------------
# 3. 오프라인 마이그레이션 (기존 유지)
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
# 4. PostGIS 안전 옵션 (autogenerate에서 무시할 객체) (기존 유지)
# ----------------------------------------------------
def include_object(object, name, type_, reflected, compare_to):
    """
    Alembic autogenerate 시 PostGIS 시스템 테이블 무시
    """
    if type_ == "table" and name in ("spatial_ref_sys", "geometry_columns", "geography_columns"):
        print(f"[INFO] Alembic autogenerate 무시: {name}")
        return False
    return True

# ----------------------------------------------------
# 5. 마이그레이션 실행 (동기) (기존 유지)
# ----------------------------------------------------
def do_run_migrations(connection):
    """동기식으로 Alembic 마이그레이션 실행"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,  # ← PostGIS 안전 옵션 적용
    )
    with context.begin_transaction():
        context.run_migrations()

# ----------------------------------------------------
# 6. 비동기 마이그레이션 (🌟 내부 수정)
# ----------------------------------------------------
async def run_async_migrations(connectable):
    """비동기 마이그레이션 실행 헬퍼"""
    async with connectable.connect() as connection:
        print("[DEBUG] 비동기 연결 생성 완료, 마이그레이션 실행 중...")
        await connection.run_sync(do_run_migrations)

async def run_migrations_online_async():
    """비동기 DB 엔진을 생성하고 마이그레이션 실행"""

    database_url = config.get_main_option("sqlalchemy.url")

    # DB URL에 postgressql+asyncpg:// 드라이버 명시
    if database_url and database_url.startswith("postgresql://"):
        async_db_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        async_db_url = database_url

    print(f"[DEBUG] ASYNC_DATABASE_URL being used: {async_db_url}")

    from sqlalchemy.ext.asyncio import create_async_engine

    connectable = create_async_engine(
        async_db_url,
        poolclass=pool.NullPool,
    )

    async with connectable.begin() as conn:
        await conn.run_sync(do_run_migrations)

    await connectable.dispose()
    print("[DEBUG] 비동기 마이그레이션 완료, 엔진 종료")

# ----------------------------------------------------
# 7. 온라인(비동기) 실행 래퍼 (기존 유지)
# ----------------------------------------------------
def run_migrations_online() -> None:
    """Run migrations in 'online' (async) mode."""
    asyncio.run(run_migrations_online_async())

# ----------------------------------------------------
# 8. 실행 진입점 (기존 유지)
# ----------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
