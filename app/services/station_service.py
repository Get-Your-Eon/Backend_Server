"""Service layer for Station and Charger business logic"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Station, Charger
from app.repository.station_repository import StationRepository, ChargerRepository
from app.services.kepco_client import kepco_client, KepcoAPIError
from app.services.geocoding_service import geocoding_service
from app.redis_client import get_cache, set_cache

logger = logging.getLogger(__name__)


class StationService:
    """Service for station and charger business logic"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.station_repo = StationRepository(db)
        self.charger_repo = ChargerRepository(db)
    
    async def search_stations_by_location(
        self, 
        lat: float, 
        lon: float, 
        radius_m: int
    ) -> List[Dict[str, Any]]:
        """
        Search stations by location with 3-tier caching strategy:
        1. Check Redis cache
        2. Check DB (static data only if no API call needed)
        3. Call KEPCO API if needed
        
        Args:
            lat: User latitude
            lon: User longitude
            radius_m: Search radius in meters
            
        Returns:
            List of station data with basic info for map display
        """
        # Normalize radius to predefined threshold
        actual_radius = kepco_client.get_radius_threshold(radius_m)
        
        # Step 1: Convert coordinates to address for caching/API
        addr = await geocoding_service.reverse_geocode(lat, lon)
        if not addr:
            logger.warning(f"Could not geocode coordinates: {lat}, {lon}")
            addr = ""
        
        cache_key = f"stations:location:{lat}:{lon}:{actual_radius}"
        
        # Step 2: Check Redis cache
        cached_data = await get_cache(cache_key)
        if cached_data:
            logger.info(f"Found cached station data for location {lat},{lon} radius {actual_radius}m")
            return cached_data
        
        # Step 3: Check DB for static data
        db_stations = await self.station_repo.get_by_addr(addr) if addr else []
        
        # Filter by radius and check if we need API refresh
        stations_in_radius = []
        need_api_refresh = False
        
        for station in db_stations:
            if self._is_station_in_radius(station, lat, lon, actual_radius):
                # Check if dynamic data is stale
                chargers = await self.charger_repo.get_by_station_id(station.id)
                if self._has_stale_charger_data(chargers):
                    need_api_refresh = True
                
                stations_in_radius.append(station)
        
        # Step 4: Call KEPCO API if needed (no stations found or stale data)
        if not stations_in_radius or need_api_refresh:
            logger.info(f"Refreshing station data from KEPCO API for addr: {addr}")
            try:
                await self._refresh_station_data_from_api(addr)
                # Re-query DB after API refresh
                db_stations = await self.station_repo.get_by_addr(addr) if addr else []
                stations_in_radius = [
                    station for station in db_stations 
                    if self._is_station_in_radius(station, lat, lon, actual_radius)
                ]
            except KepcoAPIError as e:
                logger.error(f"KEPCO API error: {e}")
                # Continue with stale DB data if API fails
        
        # Step 5: Format response data
        response_data = []
        for station in stations_in_radius:
            station_dict = {
                "cs_id": station.cs_id,
                "addr": station.addr or station.address,
                "cs_nm": station.cs_nm or station.name,
                "lat": station.lat,
                "longi": station.longi
            }
            response_data.append(station_dict)
        
        # Step 6: Cache results
        if response_data:
            await set_cache(cache_key, response_data, expire=300)  # 5 minutes
        
        logger.info(f"Found {len(response_data)} stations for location {lat},{lon} radius {actual_radius}m")
        return response_data
    
    async def get_station_chargers(
        self, 
        cs_id: str, 
        addr: str
    ) -> Dict[str, Any]:
        """
        Get detailed charger information for a station
        
        Args:
            cs_id: KEPCO station ID
            addr: Station address (for API fallback)
            
        Returns:
            Station details with charger specs
        """
        # Step 1: Try DB lookup by cs_id
        station = await self.station_repo.get_by_cs_id(cs_id)
        
        if station:
            chargers = await self.charger_repo.get_by_station_id(station.id)
            
            # Check if charger data is stale
            if self._has_stale_charger_data(chargers):
                logger.info(f"Refreshing charger data for station {cs_id}")
                try:
                    await self._refresh_station_data_from_api(addr)
                    # Re-fetch after refresh
                    chargers = await self.charger_repo.get_by_station_id(station.id)
                except KepcoAPIError as e:
                    logger.error(f"Failed to refresh charger data: {e}")
                    # Continue with stale data
        else:
            # Step 2: Station not in DB, try API
            logger.info(f"Station {cs_id} not found in DB, fetching from API")
            try:
                await self._refresh_station_data_from_api(addr)
                station = await self.station_repo.get_by_cs_id(cs_id)
                if station:
                    chargers = await self.charger_repo.get_by_station_id(station.id)
                else:
                    logger.warning(f"Station {cs_id} not found even after API refresh")
                    return None
            except KepcoAPIError as e:
                logger.error(f"Failed to fetch station from API: {e}")
                return None
        
        # Step 3: Format response
        if not station:
            return None
        
        # Get available charging methods
        available_methods = set()
        charger_details = []
        
        for charger in chargers:
            # Map charge_tp and cp_tp to human readable format
            charge_method = self._get_charge_method_name(charger.charge_tp, charger.cp_tp)
            if charge_method:
                available_methods.add(charge_method)
            
            charger_detail = {
                "cp_id": charger.cp_id,
                "cp_nm": charger.cp_nm or f"충전기 {charger.cp_id}",
                "charge_tp": charger.charge_tp,
                "cp_tp": charger.cp_tp,
                "cp_stat": charger.cp_stat,
                "charge_method": charge_method,
                "status_text": self._get_status_text(charger.cp_stat)
            }
            charger_details.append(charger_detail)
        
        response = {
            "cs_nm": station.cs_nm or station.name,
            "available_methods": ", ".join(sorted(available_methods)),
            "chargers": charger_details
        }
        
        return response
    
    async def _refresh_station_data_from_api(self, addr: str) -> None:
        """
        Refresh station and charger data from KEPCO API
        
        Args:
            addr: Address filter for API call
        """
        # Call KEPCO API
        raw_data = await kepco_client.get_charging_stations(addr)
        if not raw_data:
            logger.warning(f"No data returned from KEPCO API for addr: {addr}")
            return
        
        # Parse API response
        parsed_data = kepco_client.parse_charger_data(raw_data)
        stations_data = parsed_data["stations"]
        chargers_data = parsed_data["chargers"]
        
        # Update stations
        station_map = {}
        for station_data in stations_data:
            station = await self.station_repo.upsert_from_kepco_data(station_data)
            station_map[station.cs_id] = station
        
        # Update chargers
        for charger_data in chargers_data:
            cs_id = charger_data.get("cs_id")
            if cs_id in station_map:
                await self.charger_repo.upsert_from_kepco_data(charger_data, station_map[cs_id])
        
        # Update station's dynamic data timestamp
        now = datetime.utcnow()
        for station in station_map.values():
            station.dynamic_data_updated_at = now
        
        await self.db.commit()
        logger.info(f"Successfully refreshed {len(stations_data)} stations and {len(chargers_data)} chargers")
    
    def _is_station_in_radius(self, station: Station, center_lat: float, center_lon: float, radius_m: int) -> bool:
        """Check if station is within specified radius"""
        if not station.lat or not station.longi:
            return False
        
        try:
            station_lat = float(station.lat)
            station_lon = float(station.longi)
            return geocoding_service.is_within_radius(center_lat, center_lon, station_lat, station_lon, radius_m)
        except (ValueError, TypeError):
            logger.warning(f"Invalid coordinates for station {station.cs_id}: {station.lat}, {station.longi}")
            return False
    
    def _has_stale_charger_data(self, chargers: List[Charger], threshold_minutes: int = 30) -> bool:
        """Check if any charger has stale dynamic data"""
        if not chargers:
            return True
        
        threshold_time = datetime.utcnow() - timedelta(minutes=threshold_minutes)
        
        for charger in chargers:
            if not charger.stat_update_datetime or charger.stat_update_datetime < threshold_time:
                return True
        
        return False
    
    def _get_charge_method_name(self, charge_tp: Optional[str], cp_tp: Optional[str]) -> Optional[str]:
        """Convert KEPCO codes to human readable charging method names"""
        if not charge_tp or not cp_tp:
            return None
        
        # charge_tp: 1=완속, 2=급속
        speed = "완속" if charge_tp == "1" else "급속" if charge_tp == "2" else f"타입{charge_tp}"
        
        # cp_tp: 1=B타입(5핀), 2=C타입(5핀), 3=BC타입(5핀), 4=BC타입(7핀), 
        #        5=C차데모, 6=AC3상, 7=DC콤보, 8=DC차데모+DC콤보
        connector_map = {
            "1": "B타입(5핀)",
            "2": "C타입(5핀)", 
            "3": "BC타입(5핀)",
            "4": "BC타입(7핀)",
            "5": "C차데모",
            "6": "AC3상",
            "7": "DC콤보",
            "8": "DC차데모+DC콤보"
        }
        
        connector = connector_map.get(cp_tp, f"타입{cp_tp}")
        
        return f"{speed} {connector}"
    
    def _get_status_text(self, cp_stat: Optional[str]) -> str:
        """Convert KEPCO status code to human readable text"""
        status_map = {
            "1": "충전가능",
            "2": "충전중", 
            "3": "고장/점검",
            "4": "통신장애",
            "5": "통신미연결"
        }
        
        return status_map.get(cp_stat, "상태불명")