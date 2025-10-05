import os
import sys
from dotenv import load_dotenv
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# ----------------------------------------------------
# 1. 환경 설정 및 모델 임포트
# ----------------------------------------------------

# .env 파일 로드 (DB URL 환경 변수를 사용하기 위해 필수)
load_dotenv()

# 프로젝트 루트 경로를 시스템 경로에 추가합니다.
# 이를 통해 app/models.py를 임포트할 수 있습니다.
sys.path.append(os.getcwd())

# 사용자님이 정의한 Base 모델을 임포트합니다.
from app.models import Base
# ----------------------------------------------------


# Alembic Config 객체
config = context.config

# 로깅 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ----------------------------------------------------
# 2. 마이그레이션 대상 메타데이터 설정
# ----------------------------------------------------
# Alembic이 변경 사항을 감지할 SQLAlchemy 모델의 MetaData를 지정합니다.
# **중복 제거 및 Base.metadata로 설정 완료**
target_metadata = Base.metadata
# ----------------------------------------------------


# 오프라인 마이그레이션 모드 함수
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # alembic.ini의 sqlalchemy.url에 설정된 환경 변수 (DATABASE_URL)를 가져옵니다.
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# 온라인 마이그레이션 모드 함수
def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = config.get_main_option("sqlalchemy.url")
    print(f"DEBUG: Alembic이 읽은 URL: {url}")

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()