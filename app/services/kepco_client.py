"""KEPCO API client for EV charging station data"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class KepcoAPIError(Exception):
    """KEPCO API related errors"""
    pass


class KepcoAPIClient:
    """Client for KEPCO EV charging station API"""
    
    def __init__(self):
        self.base_url = "https://bigdata.kepco.co.kr/openapi/v1"
        self.api_key = settings.KEPCO_API_KEY
        self.timeout = float(settings.EXTERNAL_STATION_API_TIMEOUT_SEED_SECONDS)
        self.api_key_param_name = settings.EXTERNAL_STATION_API_KEY_PARAM_NAME
        self.return_type = settings.EXTERNAL_STATION_API_RETURN_TYPE
        
    async def get_charging_stations(self, addr: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch charging station data from KEPCO API
        
        Args:
            addr: Address filter (optional, e.g., "전라남도 나주시 빛가람동")
            
        Returns:
            List of charging station/charger data
            
        Raises:
            KepcoAPIError: If API request fails
        """
        if not self.api_key:
            raise KepcoAPIError("KEPCO API key not configured")
            
        params = {
            self.api_key_param_name: self.api_key,
            "returnType": self.return_type
        }
        
        if addr:
            params["addr"] = addr
            
        url = f"{self.base_url}/EVchargeManage.do"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"Requesting KEPCO API: {url} with addr={addr}")
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                # KEPCO API returns data in 'data' field
                if "data" not in data:
                    logger.warning(f"Unexpected KEPCO API response format: {data.keys()}")
                    return []
                    
                charger_data = data["data"]
                logger.info(f"Received {len(charger_data)} charger records from KEPCO API")
                
                return charger_data
                
        except httpx.HTTPError as e:
            logger.error(f"KEPCO API HTTP error: {e}")
            raise KepcoAPIError(f"API request failed: {e}")
        except Exception as e:
            logger.error(f"KEPCO API unexpected error: {e}")
            raise KepcoAPIError(f"Unexpected error: {e}")
    
    def parse_charger_data(self, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Parse raw KEPCO API response into structured station/charger data
        
        Args:
            raw_data: Raw data from KEPCO API
            
        Returns:
            Dict with 'stations' and 'chargers' keys containing parsed data
        """
        stations = {}
        chargers = []
        
        for item in raw_data:
            # Extract station data
            cs_id = item.get("csId")
            if cs_id and cs_id not in stations:
                stations[cs_id] = {
                    "cs_id": cs_id,
                    "cs_nm": item.get("csNm", ""),
                    "addr": item.get("addr", ""),
                    "lat": item.get("lat", ""),
                    "longi": item.get("longi", ""),
                }
            
            # Extract charger data
            charger = {
                "cp_id": item.get("cpId"),
                "cp_nm": item.get("cpNm", ""),
                "charge_tp": item.get("chargeTp", ""),  # 1:완속, 2:급속
                "cp_tp": item.get("cpTp", ""),  # 충전방식
                "cp_stat": item.get("cpStat", ""),  # 상태코드
                "kepco_stat_update_datetime": item.get("statUpdateDatetime", ""),
                "cs_id": cs_id,  # Foreign key to station
            }
            chargers.append(charger)
        
        return {
            "stations": list(stations.values()),
            "chargers": chargers
        }
    
    @staticmethod
    def get_radius_threshold(requested_radius: int) -> int:
        """
        Map requested radius to predefined thresholds
        
        Args:
            requested_radius: Requested radius in meters
            
        Returns:
            Appropriate threshold radius (500, 1000, 3000, 5000, 10000)
        """
        thresholds = [500, 1000, 3000, 5000, 10000]
        
        for threshold in thresholds:
            if requested_radius <= threshold:
                return threshold
                
        return 10000  # Max threshold
    
    @staticmethod
    def is_dynamic_data_stale(stat_update_datetime: Optional[datetime], threshold_minutes: int = 30) -> bool:
        """
        Check if dynamic data (charger status) is stale and needs refresh
        
        Args:
            stat_update_datetime: Last update time of dynamic data
            threshold_minutes: Staleness threshold in minutes (default: 30)
            
        Returns:
            True if data is stale or missing
        """
        if not stat_update_datetime:
            return True
            
        threshold = datetime.utcnow() - timedelta(minutes=threshold_minutes)
        return stat_update_datetime < threshold


# Global instance
kepco_client = KepcoAPIClient()