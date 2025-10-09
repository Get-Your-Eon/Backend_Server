import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text
from geoalchemy2.functions import ST_GeomFromText
from sqlalchemy.orm import sessionmaker
# [삭제] 수동 등록 코드는 asyncpg에 적합하지 않아 AttributeError를 유발합니다.
# from sqlalchemy.dialects import registry
# registry.register("postgresql.asyncpg", "asyncpg", "DBAPI")

# [수정] asyncpg 드라이버가 SQLAlchemy에 올바르게 등록되도록
# create_async_engine 호출 이전에 명시적으로 임포트합니다.
import asyncpg

# 프로젝트 내부 모듈 임포트
# NOTE: 이 스크립트는 프로젝트 루트에서 실행되므로 절대 경로 임포트를 사용합니다.
from app.config import settings
from app.models import Base, Station, Charger
from app.mock_api import MOCK_STATIONS_DATA # Mock API에서 초기 데이터 로드

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 비동기 엔진 생성
DATABASE_URL = settings.DATABASE_URL # -> "postgresql+asyncpg://..."
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
)
AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def init_db():
    """데이터베이스 테이블 생성 및 초기 데이터 삽입"""
    logger.info("Starting database initialization...")

    # 1. 테이블 생성 (데이터베이스에 존재하지 않는 경우)
    async with engine.begin() as conn:
        # PostgreSQL에 PostGIS 확장이 설치되어 있는지 확인하고 활성화
        # NOTE: 이 부분에서 데이터베이스 연결 권한 문제가 발생할 수 있습니다.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))

        # 모든 테이블 생성
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully.")

    # 2. 초기 데이터 삽입
    async with AsyncSessionLocal() as session:
        try:
            # Station 데이터 삽입
            for mock_station in MOCK_STATIONS_DATA:
                station_code = mock_station["station_code"]

                # 중복 삽입 방지를 위해 station_code로 검색
                existing_station = await session.execute(
                    select(Station).where(Station.station_code == station_code)
                )
                if existing_station.scalar_one_or_none():
                    logger.info(f"Station {station_code} already exists. Skipping.")
                    continue

                # Point 객체 생성 및 WKT(Well-Known Text)를 PostGIS 형식으로 변환
                wkt_point = f"POINT({mock_station['longitude']} {mock_station['latitude']})"

                new_station = Station(
                    station_code=station_code,
                    name=mock_station["name"],
                    address=mock_station["address"],
                    provider=mock_station["provider"],
                    location=ST_GeomFromText(wkt_point, 4326), # SRID 4326 (WGS 84)
                )
                session.add(new_station)
                await session.flush() # ID를 얻기 위해 강제로 DB에 쓰기

                # Charger 데이터 삽입 (기본 충전기 하나씩 추가)
                new_charger = Charger(
                    station_id=new_station.id,
                    charger_code="1", # 기본 충전기 코드
                    charger_type="DC Combo",
                    connector_type="Type 1",
                    output_kw=50.0,
                    status_code=1 # 사용 가능
                )
                session.add(new_charger)

            await session.commit()
            logger.info(f"Successfully inserted {len(MOCK_STATIONS_DATA)} stations and initial chargers.")

        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to initialize database: {e}")
            raise

if __name__ == "__main__":
    # main 함수가 비동기 함수이므로 asyncio.run으로 실행합니다.
    asyncio.run(init_db())