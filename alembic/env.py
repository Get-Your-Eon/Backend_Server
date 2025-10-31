import os
import sys
import asyncio
from dotenv import load_dotenv
from logging.config import fileConfig

# Import synchronous engine helpers (Alembic prefers sync connections)
from sqlalchemy import create_engine, pool
from alembic import context

# ----------------------------------------------------
# 1. Configuration and model imports
# ----------------------------------------------------

# Load .env file (the main app already does this, but keep it to allow
# running alembic standalone)
load_dotenv()

# Add project root to sys.path so that app modules can be imported
sys.path.append(os.getcwd())

# Import Base model metadata (Base is defined in app.models)
from app.models import Base

# Import settings from application config
from app.core.config import settings

# Alembic Config 객체
config = context.config

# 로깅 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ----------------------------------------------------
# A. Ensure Alembic uses a synchronous DB URL
# ----------------------------------------------------
db_url_from_ini = config.get_main_option("sqlalchemy.url")

# If alembic.ini does not contain a URL, fall back to settings.DATABASE_URL
if not db_url_from_ini:
    # 🌟 [수정] settings에서 직접 DATABASE_URL을 가져와 사용
    db_url_from_ini = settings.DATABASE_URL

# If the project DATABASE_URL uses the asyncpg driver prefix,
# convert it to a sync URL for Alembic (postgresql+asyncpg:// -> postgresql://)
if db_url_from_ini and db_url_from_ini.startswith("postgresql+asyncpg://"):
    db_url_from_ini = db_url_from_ini.replace("postgresql+asyncpg://", "postgresql://", 1)

if db_url_from_ini:
    # Trim whitespace and set sqlalchemy.url for Alembic
    config.set_main_option("sqlalchemy.url", db_url_from_ini.strip())


# ----------------------------------------------------
# 2. Target metadata (keep existing behavior)
# ----------------------------------------------------
target_metadata = Base.metadata

# ----------------------------------------------------
# 3. Offline migration (keep existing behavior)
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
# 4. PostGIS safety options (exclude system tables from autogenerate)
# ----------------------------------------------------
def include_object(object, name, type_, reflected, compare_to):
    """
    Exclude PostGIS system tables when running Alembic autogenerate.
    """
    if type_ == "table" and name in ("spatial_ref_sys", "geometry_columns", "geography_columns"):
        print(f"[INFO] Alembic autogenerate skip: {name}")
        return False
    return True

# ----------------------------------------------------
# 5. Run migrations synchronously (used by the sync runner)
# ----------------------------------------------------
def do_run_migrations(connection):
    """Run Alembic migrations using a synchronous connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,  # ← PostGIS 안전 옵션 적용
    )
    with context.begin_transaction():
        context.run_migrations()

# ----------------------------------------------------
# 6. Asynchronous migration helpers
# ----------------------------------------------------
async def run_async_migrations(connectable):
    """비동기 마이그레이션 실행 헬퍼"""
    async with connectable.connect() as connection:
        print("[DEBUG] async connection opened, running migrations...")
        await connection.run_sync(do_run_migrations)

async def run_migrations_online_async():
    """Create an async DB engine and run migrations."""

    database_url = config.get_main_option("sqlalchemy.url")

    # If the sync URL was provided, convert it back to an async URL
    if database_url and database_url.startswith("postgresql://"):
        async_db_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        async_db_url = database_url
    print(f"[DEBUG] DATABASE_URL: {database_url}")
    print(f"[DEBUG] ASYNC_DATABASE_URL being used: {async_db_url}")

    from sqlalchemy.ext.asyncio import create_async_engine

    # asyncpg.connect does not accept an 'sslmode' keyword argument.
    # If the URL contains sslmode=<...> (commonly added for libpq tools),
    # remove it from the URL and instruct asyncpg to use SSL via connect_args.
    connect_args = {}
    if async_db_url and "sslmode=" in async_db_url:
        import urllib.parse as _urlparse

        parsed = _urlparse.urlparse(async_db_url)
        qs = _urlparse.parse_qs(parsed.query, keep_blank_values=True)
        if "sslmode" in qs:
            qs.pop("sslmode", None)
            new_query = _urlparse.urlencode(qs, doseq=True)
            async_db_url = _urlparse.urlunparse(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
            )
            # Ask asyncpg to use SSL. asyncpg expects 'ssl' (bool or SSLContext),
            # not 'sslmode'. Using True will create a default SSLContext internally.
            connect_args["ssl"] = True

    print(f"[DEBUG] final ASYNC_DATABASE_URL: {async_db_url}")

    # Avoid passing None for connect_args; SQLAlchemy expects a dict if provided.
    create_kwargs = {"poolclass": pool.NullPool}
    if connect_args:
        create_kwargs["connect_args"] = connect_args

    connectable = create_async_engine(
        async_db_url,
        **create_kwargs,
    )

    async with connectable.begin() as conn:
        await conn.run_sync(do_run_migrations)

    await connectable.dispose()
    print("[DEBUG] async migrations complete, engine disposed")

# ----------------------------------------------------
# 7. Online (async) runner wrapper
# ----------------------------------------------------
def run_migrations_online() -> None:
    """Run migrations in 'online' (async) mode."""
    asyncio.run(run_migrations_online_async())

# ----------------------------------------------------
# 8. Execution entry point
# ----------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
