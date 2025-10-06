import random
import asyncio
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# --- 초기 DB 삽입을 위한 Mock Station Data ---
# init_db.py에서 임포트하여 사용됩니다.
MOCK_STATIONS_DATA: List[Dict[str, Any]] = [
    {
        "station_code": "ST0001",
        "name": "강남역 충전소",
        "address": "서울 강남구 역삼동 812-1",
        "provider": "A사",
        "latitude": 37.4979,
        "longitude": 127.0276
    },
    {
        "station_code": "ST0002",
        "name": "여의도 파크 충전소",
        "address": "서울 영등포구 여의도동 2",
        "provider": "B사",
        "latitude": 37.5255,
        "longitude": 126.9250
    },
    {
        "station_code": "ST0003",
        "name": "홍대입구역 충전소",
        "address": "서울 마포구 동교동 167-1",
        "provider": "A사",
        "latitude": 37.5566,
        "longitude": 126.9238
    },
    {
        "station_code": "ST0004",
        "name": "잠실 롯데 충전소",
        "address": "서울 송파구 올림픽로 300",
        "provider": "C사",
        "latitude": 37.5135,
        "longitude": 127.1001
    },
    {
        "station_code": "ST0005",
        "name": "구로 디지털단지 충전소",
        "address": "서울 구로구 구로동 182-13",
        "provider": "B사",
        "latitude": 37.4851,
        "longitude": 126.8953
    }
]

# --- API 폴백을 위한 Mock 함수 ---

async def get_mock_stations(latitude: float, longitude: float, radius_km: float) -> List[Dict[str, Any]]:
    """
    주변 충전소 검색 API의 Mock Fallback 함수.
    실제 DB나 캐시에서 데이터를 찾지 못했을 경우 사용됩니다.
    """
    logger.info(f"Mock API: Retrieving stations near ({latitude}, {longitude}) with radius {radius_km}km.")
    await asyncio.sleep(0.1) # 비동기 API 호출 흉내

    # Mock 데이터에 charger 정보를 추가합니다 (router.py의 StationRead 스키마와 일치하도록)
    mock_stations_with_chargers = []
    for station in MOCK_STATIONS_DATA:
        # DB에서 삽입할 때 사용한 Charger 구조를 모방합니다.
        chargers = [{
            "id": random.randint(1000, 2000), # 임시 ID
            "station_id": 0, # 더미 값
            "charger_code": "1",
            "charger_type": "DC Combo",
            "connector_type": "Type 1",
            "output_kw": 50.0,
            "status_code": random.choice([1, 2, 3]), # 1: 사용가능, 2: 충전중, 3: 고장
        }]
        mock_stations_with_chargers.append({**station, "chargers": chargers})

    return mock_stations_with_chargers


async def get_mock_charger_status(station_code: str, charger_code: str) -> Optional[int]:
    """
    특정 충전기의 실시간 상태를 가져오는 Mock 함수.
    router.py의 update_charger_status 엔드포인트에서 사용됩니다.
    """
    logger.info(f"Mock API: Getting status for Station: {station_code}, Charger: {charger_code}")
    await asyncio.sleep(0.05) # 비동기 API 호출 흉내

    if station_code in ["ST0001", "ST0003", "ST0005"]:
        # Mocking: 랜덤 상태 (1: 사용가능, 2: 충전중, 3: 고장)
        return random.choices([1, 2, 3], weights=[70, 20, 10], k=1)[0]

    if station_code == "ST0002":
        return 2 # 항상 충전 중

    if station_code == "ST0004":
        return 3 # 항상 고장

    return None # 찾을 수 없음