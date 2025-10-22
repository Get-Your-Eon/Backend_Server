"""Repository for Station and Charger data access"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.orm import selectinload
from geoalchemy2.functions import ST_DWithin, ST_GeogFromText, ST_SetSRID, ST_MakePoint

from app.models import Station, Charger

logger = logging.getLogger(__name__)


class StationRepository:
    """Repository for Station data operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_cs_id(self, cs_id: str) -> Optional[Station]:
        """Get station by KEPCO station ID"""
        result = await self.db.execute(
            select(Station)
            .options(selectinload(Station.chargers))
            .where(Station.cs_id == cs_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_addr(self, addr: str) -> List[Station]:
        """Get stations by address (for cache lookup)"""
        result = await self.db.execute(
            select(Station)
            .options(selectinload(Station.chargers))
            .where(Station.addr.ilike(f"%{addr}%"))
        )
        return result.scalars().all()
    
    async def get_within_radius(self, lat: float, lon: float, radius_m: int) -> List[Station]:
        """
        Get stations within specified radius using PostGIS
        
        Args:
            lat: Center latitude
            lon: Center longitude  
            radius_m: Radius in meters
            
        Returns:
            List of stations within radius
        """
        # Create point from lat/lon
        center_point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        
        result = await self.db.execute(
            select(Station)
            .options(selectinload(Station.chargers))
            .where(
                and_(
                    Station.location.isnot(None),
                    ST_DWithin(Station.location, center_point, radius_m)
                )
            )
            .order_by(
                func.ST_Distance(Station.location, center_point)
            )
        )
        return result.scalars().all()
    
    async def upsert_from_kepco_data(self, station_data: Dict[str, Any]) -> Station:
        """
        Insert or update station from KEPCO API data
        
        Args:
            station_data: Parsed station data from KEPCO API
            
        Returns:
            Created or updated Station instance
        """
        cs_id = station_data["cs_id"]
        existing = await self.get_by_cs_id(cs_id)
        
        now = datetime.utcnow()
        
        if existing:
            # Update existing station
            existing.cs_nm = station_data.get("cs_nm", existing.cs_nm)
            existing.addr = station_data.get("addr", existing.addr)
            existing.lat = station_data.get("lat", existing.lat)
            existing.longi = station_data.get("longi", existing.longi)
            existing.static_data_updated_at = now
            existing.updated_at = now
            
            # Update PostGIS location if coordinates available
            if existing.lat and existing.longi:
                try:
                    lat_float = float(existing.lat)
                    lon_float = float(existing.longi)
                    point_wkt = f"SRID=4326;POINT({lon_float} {lat_float})"
                    await self.db.execute(
                        text("UPDATE stations SET location = ST_GeomFromEWKT(:point) WHERE id = :station_id"),
                        {"point": point_wkt, "station_id": existing.id}
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to update location for station {cs_id}: {e}")
            
            station = existing
        else:
            # Create new station
            station = Station(
                station_code=cs_id,  # Use cs_id as station_code for uniqueness
                name=station_data.get("cs_nm", ""),
                cs_id=cs_id,
                cs_nm=station_data.get("cs_nm", ""),
                addr=station_data.get("addr", ""),
                lat=station_data.get("lat", ""),
                longi=station_data.get("longi", ""),
                provider="KEPCO",
                static_data_updated_at=now,
                created_at=now,
                updated_at=now
            )
            
            # Set PostGIS location if coordinates available
            if station.lat and station.longi:
                try:
                    lat_float = float(station.lat)
                    lon_float = float(station.longi)
                    point_wkt = f"SRID=4326;POINT({lon_float} {lat_float})"
                    station.location = text(f"ST_GeomFromEWKT('{point_wkt}')")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to set location for new station {cs_id}: {e}")
            
            self.db.add(station)
        
        await self.db.flush()  # Get ID for new stations
        return station


class ChargerRepository:
    """Repository for Charger data operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_cp_id(self, cp_id: str) -> Optional[Charger]:
        """Get charger by KEPCO charger ID"""
        result = await self.db.execute(
            select(Charger).where(Charger.cp_id == cp_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_station_id(self, station_id: int) -> List[Charger]:
        """Get all chargers for a station"""
        result = await self.db.execute(
            select(Charger).where(Charger.station_id == station_id)
        )
        return result.scalars().all()
    
    async def get_by_cs_id(self, cs_id: str) -> List[Charger]:
        """Get all chargers for a station by KEPCO station ID"""
        result = await self.db.execute(
            select(Charger).where(Charger.cs_id == cs_id)
        )
        return result.scalars().all()
    
    async def upsert_from_kepco_data(self, charger_data: Dict[str, Any], station: Station) -> Charger:
        """
        Insert or update charger from KEPCO API data
        
        Args:
            charger_data: Parsed charger data from KEPCO API
            station: Parent station instance
            
        Returns:
            Created or updated Charger instance
        """
        cp_id = charger_data["cp_id"]
        existing = await self.get_by_cp_id(cp_id)
        
        now = datetime.utcnow()
        
        # Parse KEPCO datetime string to datetime object
        kepco_datetime_str = charger_data.get("kepco_stat_update_datetime", "")
        stat_update_datetime = None
        if kepco_datetime_str:
            try:
                # Assuming KEPCO uses format like "2023-10-23 14:30:00"
                stat_update_datetime = datetime.strptime(kepco_datetime_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                logger.warning(f"Failed to parse KEPCO datetime: {kepco_datetime_str}")
        
        if existing:
            # Update existing charger
            existing.cp_nm = charger_data.get("cp_nm", existing.cp_nm)
            existing.charge_tp = charger_data.get("charge_tp", existing.charge_tp)
            existing.cp_tp = charger_data.get("cp_tp", existing.cp_tp)
            existing.cp_stat = charger_data.get("cp_stat", existing.cp_stat)  # Dynamic data
            existing.kepco_stat_update_datetime = kepco_datetime_str
            existing.stat_update_datetime = stat_update_datetime
            existing.updated_at = now
            
            charger = existing
        else:
            # Create new charger
            charger = Charger(
                station_id=station.id,
                charger_code=cp_id,  # Use cp_id as charger_code
                cp_id=cp_id,
                cp_nm=charger_data.get("cp_nm", ""),
                charge_tp=charger_data.get("charge_tp", ""),
                cp_tp=charger_data.get("cp_tp", ""),
                cp_stat=charger_data.get("cp_stat", ""),
                kepco_stat_update_datetime=kepco_datetime_str,
                stat_update_datetime=stat_update_datetime,
                cs_id=charger_data.get("cs_id", ""),
                created_at=now,
                updated_at=now
            )
            
            self.db.add(charger)
        
        return charger
    
    async def get_stale_chargers(self, threshold_minutes: int = 30) -> List[Charger]:
        """
        Get chargers with stale dynamic data (status updates older than threshold)
        
        Args:
            threshold_minutes: Staleness threshold in minutes
            
        Returns:
            List of chargers needing status updates
        """
        from datetime import timedelta
        threshold_time = datetime.utcnow() - timedelta(minutes=threshold_minutes)
        
        result = await self.db.execute(
            select(Charger).where(
                or_(
                    Charger.stat_update_datetime.is_(None),
                    Charger.stat_update_datetime < threshold_time
                )
            )
        )
        return result.scalars().all()