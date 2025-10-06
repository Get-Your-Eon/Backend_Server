import random
import asyncio
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

MOCK_STATIONS_DATA: List[Dict[str, Any]] = [
    {"station_code": "ST0001", "name": "강남역 충전소", "address": "서울 강남구 역삼동 812-1", "provider": "A사", "latitude": 37.4979, "longitude": 127.0276},
    {"station_code": "ST0002", "name": "여의도 파크 충전소", "address": "서울 영등포구 여의도동 2", "provider": "B사", "latitude": 37.5255, "longitude": 126.9250},
    {"station_code": "ST0003", "name": "홍대입구역 충전소", "address": "서울 마포구 동교동 167-1", "provider": "A사", "latitude": 37.5566, "longitude": 126.9238},
    {"station_code": "ST0004", "name": "잠실 롯데 충전소", "address": "서울 송파구 올림픽로 300", "provider": "C사", "latitude": 37.5135, "longitude": 127.1001},
    {"station_code": "ST0005", "name": "구로 디지털단지 충전소", "address": "서울 구로구 구로동 182-13", "provider": "B사", "latitude": 37.4851, "longitude": 126.8953},
]

# -----------------------------
# 1. 공공 API 호출 Mock
# -----------------------------
async def fetch_public_api_stations(lat: float, lng: float) -> List[Dict[str, Any]]:
    """
    공공 API 호출 Mock (fallback)
    """
    logger.info(f"Fetching stations from public API for ({lat}, {lng})")
    await asyncio.sleep(0.1)
    return MOCK_STATIONS_DATA

# -----------------------------
# 2. get_mock_stations 정의
# -----------------------------
async def get_mock_stations(lat: float, lng: float, radius_km: float = 5.0) -> List[Dict[str, Any]]:
    """
    기존 fetch_public_api_stations와 동일 기능, station_service.py에서 사용
    """
    logger.info(f"Retrieving mock stations near ({lat}, {lng}) with radius {radius_km}km")
    await asyncio.sleep(0.1)

    # Charger 정보 포함
    mock_stations_with_chargers = []
    for station in MOCK_STATIONS_DATA:
        chargers = [{
            "id": random.randint(1000, 2000),
            "station_id": 0,
            "charger_code": "1",
            "charger_type": "DC Combo",
            "connector_type": "Type 1",
            "output_kw": 50.0,
            "status_code": random.choice([1, 2, 3]),
        }]
        mock_stations_with_chargers.append({**station, "chargers": chargers})

    return mock_stations_with_chargers

# -----------------------------
# 3. 충전기 상태 Mock
# -----------------------------
async def get_mock_charger_status(station_code: str, charger_code: str) -> Optional[int]:
    logger.info(f"Getting mock status for {station_code}/{charger_code}")
    await asyncio.sleep(0.05)
    return random.choice([1, 2, 3])
