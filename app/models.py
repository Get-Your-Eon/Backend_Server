from __future__ import annotations # 타입 힌트 오류 방지
import datetime
import os # [수정] os 모듈 임포트: os.environ.get 사용을 위해 추가
from typing import AsyncGenerator, Optional, List

# SQLAlchemy 2.0 비동기 및 Declarative Base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import String, DateTime, Integer, ForeignKey, func, Column, Text, Float, UniqueConstraint, Numeric

# DB 드라이버 임포트
import asyncpg

# GeoAlchemy2 (공간 데이터 타입)
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_Y, ST_X
from geoalchemy2.shape import to_shape

# 설정 가져오기
from .config import settings

# -----------------------------------------------------------
# 1. DB 연결 설정 및 Base
# -----------------------------------------------------------

# 환경 변수에 따라 DB Echo 설정
DB_ECHO = os.environ.get("DB_ECHO", "False").lower() in ('true', '1', 't')

ASYNC_DATABASE_URL = settings.DATABASE_URL
print(f"[DEBUG] ASYNC_DATABASE_URL being used: {ASYNC_DATABASE_URL}")

# 비동기 DB 엔진 생성
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=DB_ECHO,
    future=True
)

# 비동기 세션 팩토리 생성 (AsyncSession을 반환)
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Declarative Base: 모든 모델 클래스의 부모
class Base(DeclarativeBase):
    pass

# Alembic 환경 파일(env.py)에서 필요함
metadata = Base.metadata

# DB 세션 의존성 주입 함수
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """비동기 DB 세션을 제공하는 제너레이터."""
    async with AsyncSessionLocal() as session:
        yield session

# -----------------------------------------------------------
# 2. 모델 정의 (Model Definitions)
# -----------------------------------------------------------

class Station(Base):
    """전기차 충전소 정보 모델"""
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, comment="충전소 DB 내부 고유 ID")
    station_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, comment="공공데이터 API 충전소 고유 코드")
    name: Mapped[str] = mapped_column(String(200), index=True, comment="충전소 이름")
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="충전소 상세 주소 정보")
    provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="충전소 운영사 정보")

    # PostGIS: Geometry 타입은 Mapped 대신 Column을 사용해야 GeoAlchemy2와 호환됩니다.
    location = Column(Geometry(geometry_type='POINT', srid=4326), index=True, comment="PostGIS 위도/경도 위치 (POINT)")

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), comment="레코드 생성 시각")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), comment="레코드 최종 수정 시각")

    # 관계 정의: Station 하나는 여러 Charger를 가집니다 (1:N)
    chargers: Mapped[List['Charger']] = relationship(back_populates="station", cascade="all, delete-orphan")

    # Pydantic 스키마 (StationRead)와 호환되도록 위도/경도 속성을 추가합니다.
    @hybrid_property
    def latitude(self) -> Optional[float]:
        """location 컬럼에서 위도(Y)를 추출합니다. (Python 객체 접근 시)"""
        if self.location is not None:
            try:
                return to_shape(self.location).y
            except Exception:
                return None
        return None

    @latitude.expression
    def latitude(cls):
        """location 컬럼에서 위도(Y)를 추출하는 SQL 표현식입니다. (쿼리 사용 시)"""
        return ST_Y(cls.location)

    @hybrid_property
    def longitude(self) -> Optional[float]:
        """location 컬럼에서 경도(X)를 추출합니다. (Python 객체 접근 시)"""
        if self.location is not None:
            try:
                return to_shape(self.location).x
            except Exception:
                return None
        return None

    @longitude.expression
    def longitude(cls):
        """location 컬럼에서 경도(X)를 추출하는 SQL 표현식입니다. (쿼리 사용 시)"""
        return ST_X(cls.location)


    def __repr__(self) -> str:
        return f"Station(id={self.id!r}, code={self.station_code!r})"


class Charger(Base):
    """개별 충전기 정보 모델 (Station에 종속)"""
    __tablename__ = "chargers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, comment="충전기 DB 내부 고유 ID")

    # Foreign Key
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True, comment="소속 충전소 DB ID")

    # 충전기 고유 식별자 (Station 내에서)
    charger_code: Mapped[str] = mapped_column(String(50), comment="충전소 내 충전기 코드 (예: '1', '2')")

    # 충전기 스펙
    charger_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="충전기 종류 (예: 급속, 완속)")
    connector_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="커넥터 타입 (예: DC차데모, AC3상)")

    # output_kw: Float 사용
    output_kw: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="충전기 출력 (kW)")

    # 실시간 상태
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="충전기 상태 코드 (0: 사용가능, 1: 충전중 등)")

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), comment="레코드 생성 시각")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), comment="레코드 최종 수정 시각")

    # 복합 유니크 제약조건 (Station 내 Charger Code는 고유해야 함)
    __table_args__ = (
        UniqueConstraint('station_id', 'charger_code', name='_station_charger_uc'),
    )

    # 관계 정의: Charger는 하나의 Station에 종속됩니다.
    station: Mapped['Station'] = relationship(back_populates="chargers")

    def __repr__(self) -> str:
        return f"Charger(id={self.id!r}, code={self.charger_code!r}, status={self.status_code!r})"


class ApiLog(Base):
    """외부 API 호출 로그 모델"""
    __tablename__ = "api_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(255), comment="요청 엔드포인트")
    method: Mapped[str] = mapped_column(String(10), comment="HTTP 메서드")
    api_type: Mapped[str] = mapped_column(String(50), comment="API 타입 (예: StationInfo, StatusUpdate)")
    status_code: Mapped[int] = mapped_column(Integer, comment="HTTP 응답 상태 코드")
    response_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="외부 API 응답 코드")