from __future__ import annotations
import datetime
from typing import List, Optional
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy import Integer, String, Text, Float, DateTime, ForeignKey, UniqueConstraint, Column
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from .config import settings

Base = declarative_base()

# -----------------------------------------------------
# 모델 정의
# -----------------------------------------------------
class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    station_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location = Column(Geometry(geometry_type='POINT', srid=4326), index=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    chargers: Mapped[List['Charger']] = relationship(back_populates="station", cascade="all, delete-orphan")

    @property
    def latitude(self) -> Optional[float]:
        if self.location:
            return to_shape(self.location).y
        return None

    @property
    def longitude(self) -> Optional[float]:
        if self.location:
            return to_shape(self.location).x
        return None


class Charger(Base):
    __tablename__ = "chargers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True)
    charger_code: Mapped[str] = mapped_column(String(50))
    charger_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    connector_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    output_kw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint('station_id', 'charger_code', name='_station_charger_uc'),)

    station: Mapped['Station'] = relationship(back_populates="chargers")


class ApiLog(Base):
    __tablename__ = "api_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(10))
    api_type: Mapped[str] = mapped_column(String(50))
    status_code: Mapped[int] = mapped_column(Integer)
    response_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_msg: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


# -----------------------------------------------------
# AsyncSession 정의 (get_async_session)
# -----------------------------------------------------
DATABASE_URL = settings.DATABASE_URL
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_async_session() -> AsyncSession:
    async with async_session() as session:
        yield session
