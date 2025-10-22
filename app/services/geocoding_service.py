"""Geocoding service for lat/lon to address mapping"""

import logging
from typing import Optional, Tuple
import httpx
import asyncio

logger = logging.getLogger(__name__)


class GeocodingService:
    """Service for converting coordinates to addresses and vice versa"""
    
    def __init__(self):
        self.timeout = 10.0
    
    async def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        """
        Convert latitude/longitude to address (시군구동 level)
        
        Uses Nominatim (OpenStreetMap) service for reverse geocoding
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Address string suitable for KEPCO API (e.g., "전라남도 나주시 빛가람동")
            None if geocoding fails
        """
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                "format": "json",
                "lat": lat,
                "lon": lon,
                "zoom": 10,  # City/district level
                "addressdetails": 1,
                "accept-language": "ko",  # Prefer Korean
            }
            
            headers = {
                "User-Agent": "EVChargingStationApp/1.0"
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                
                if "address" not in data:
                    logger.warning(f"No address found for coordinates: {lat}, {lon}")
                    return None
                
                address = data["address"]
                
                # Extract Korean administrative divisions
                # Prioritize Korean names if available
                state = (
                    address.get("state") or 
                    address.get("province") or
                    ""
                )
                city = (
                    address.get("city") or 
                    address.get("county") or
                    address.get("town") or
                    ""
                )
                district = (
                    address.get("suburb") or
                    address.get("neighbourhood") or
                    address.get("quarter") or
                    ""
                )
                
                # Build address string for KEPCO API
                addr_parts = [part for part in [state, city, district] if part]
                if not addr_parts:
                    logger.warning(f"Could not extract address components from: {address}")
                    return None
                
                result = " ".join(addr_parts)
                logger.info(f"Reverse geocoded ({lat}, {lon}) -> {result}")
                return result
                
        except Exception as e:
            logger.error(f"Reverse geocoding failed for ({lat}, {lon}): {e}")
            return None
    
    def calculate_distance_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate approximate distance between two points using Haversine formula
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in kilometers
        """
        import math
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth radius in kilometers
        r = 6371
        
        return c * r
    
    def is_within_radius(self, center_lat: float, center_lon: float, 
                        point_lat: float, point_lon: float, radius_m: int) -> bool:
        """
        Check if a point is within specified radius of center point
        
        Args:
            center_lat, center_lon: Center point coordinates
            point_lat, point_lon: Point to check
            radius_m: Radius in meters
            
        Returns:
            True if point is within radius
        """
        distance_km = self.calculate_distance_km(center_lat, center_lon, point_lat, point_lon)
        return distance_km <= (radius_m / 1000)


# Global instance
geocoding_service = GeocodingService()