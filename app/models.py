from __future__ import annotations
import datetime
from typing import List, Optional

from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

# ------------------ User ------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

# ------------------ Station ------------------
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
        return to_shape(self.location).y if self.location else None

    @property
    def longitude(self) -> Optional[float]:
        return to_shape(self.location).x if self.location else None

# ------------------ Charger ------------------
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

# ------------------ ApiLog ------------------
class ApiLog(Base):
    __tablename__ = "api_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(10))
    api_type: Mapped[str] = mapped_column(String(50))
    status_code: Mapped[int] = mapped_column(Integer)
    response_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_msg: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

# ------------------ Subsidy ------------------
class Subsidy(Base):
    __tablename__ = "subsidies"

    id = Column(Integer, primary_key=True, index=True)
    manufacturer = Column(String, index=True, nullable=False)
    model_group = Column(String, index=True, nullable=False)
    model_name = Column(String, unique=True, nullable=False)
    subsidy_national_10k_won = Column(Integer, nullable=False)
    subsidy_local_10k_won = Column(Integer, nullable=False)
    subsidy_total_10k_won = Column(Integer, nullable=False)
