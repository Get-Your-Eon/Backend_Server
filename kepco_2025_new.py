"""
KEPCO 2025 API 전용 새 구현
모든 이전 코드 제거하고 완전히 새로 작성
"""

from fastapi import Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
import httpx
import math
from datetime import datetime, timezone
from app.api.deps import frontend_api_key_required
from app.db.database import get_async_session
from app.redis_client import get_redis_client
from app.core.config import settings


async def kepco_2025_station_search_brand_new(
    lat: float = Query(..., description="위도 좌표", ge=-90, le=90),
    lon: float = Query(..., description="경도 좌표", ge=-180, le=180), 
    radius: int = Query(..., description="검색 반경(미터) - 필수", ge=100, le=10000),
    page: int = Query(1, description="페이지 번호", ge=1),
    limit: int = Query(20, description="페이지당 결과 수", ge=1, le=100),
    api_key: str = Depends(frontend_api_key_required),
    db: AsyncSession = Depends(get_async_session),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    🚀 KEPCO 2025 API 전용 - 완전히 새로운 구현
    
    이전 URL (잘못됨): /ws/chargePoint/curChargePoint
    새 URL (올바름): /EVchargeManage.do
    """
    print(f"🚀🚀🚀 KEPCO 2025 BRAND NEW IMPLEMENTATION 🚀🚀🚀")
    print(f"🚀 Time: {datetime.now(timezone.utc)}")
    print(f"🚀 Params: lat={lat}, lon={lon}, radius={radius}")
    
    try:
        # 좌표를 주소로 변환
        async def coords_to_address(lat: float, lon: float) -> str:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://nominatim.openstreetmap.org/reverse",
                        params={"format": "json", "lat": lat, "lon": lon, "addressdetails": 1},
                        headers={"User-Agent": "KEPCO-2025-EV-API"},
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        addr_dict = data.get("address", {})
                        
                        parts = []
                        if addr_dict.get("country") == "대한민국":
                            if "city" in addr_dict:
                                parts.append(addr_dict["city"])
                            if "borough" in addr_dict:
                                parts.append(addr_dict["borough"])
                            if "suburb" in addr_dict:
                                parts.append(addr_dict["suburb"])
                        
                        return " ".join(parts) if parts else f"{lat},{lon}"
                    return f"{lat},{lon}"
            except:
                return f"{lat},{lon}"
        
        # 거리 계산
        def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            try:
                R = 6371000
                lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
                c = 2 * math.asin(math.sqrt(a))
                return R * c
            except:
                return 999999
        
        # 1. 주소 변환
        search_address = await coords_to_address(lat, lon)
        print(f"🚀 검색 주소: {search_address}")
        
        # 2. KEPCO API 호출
        kepco_url = settings.EXTERNAL_STATION_API_BASE_URL
        kepco_key = settings.EXTERNAL_STATION_API_KEY
        
        print(f"🚀 KEPCO URL: {kepco_url}")
        print(f"🚀 올바른 URL인지 확인: https://bigdata.kepco.co.kr/openapi/v1/EVchargeManage.do")
        
        if not kepco_url or not kepco_key:
            raise HTTPException(status_code=500, detail="KEPCO API 설정 누락")
        
        async with httpx.AsyncClient() as client:
            kepco_response = await client.get(
                kepco_url,
                params={
                    "addr": search_address,
                    "apiKey": kepco_key,
                    "returnType": "json"
                },
                timeout=30.0
            )
            
            print(f"🚀 KEPCO 응답 상태: {kepco_response.status_code}")
            
            if kepco_response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"KEPCO API 호출 실패: {kepco_response.status_code}"
                )
            
            kepco_data = kepco_response.json()
        
        # 3. 응답 처리
        stations = []
        
        if isinstance(kepco_data, dict) and "data" in kepco_data:
            raw_data = kepco_data["data"]
            if isinstance(raw_data, list):
                for item in raw_data:
                    try:
                        station_lat = float(item.get("lat", 0))
                        station_lon = float(item.get("longi", 0))
                        
                        if station_lat == 0 or station_lon == 0:
                            continue
                        
                        distance = calculate_distance(lat, lon, station_lat, station_lon)
                        if distance > radius:
                            continue
                        
                        stations.append({
                            "station_id": item.get("csId", ""),
                            "station_name": item.get("csNm", ""),
                            "address": item.get("addr", ""),
                            "lat": station_lat,
                            "lon": station_lon,
                            "distance_m": int(distance),
                            "charger_id": item.get("cpId", ""),  
                            "charger_name": item.get("cpNm", ""),
                            "charger_status": item.get("cpStat", ""),
                            "charge_type": item.get("chargeTp", "")
                        })
                    except:
                        continue
        
        # 4. 정렬 및 반환
        stations.sort(key=lambda x: x["distance_m"])
        result_stations = stations[:limit]
        
        return {
            "message": "🚀 KEPCO 2025 NEW API SUCCESS!",
            "status": "kepco_2025_success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "search_params": {
                "lat": lat,
                "lon": lon,
                "radius": radius,
                "search_address": search_address
            },
            "result_info": {
                "total_found": len(stations),
                "returned": len(result_stations)
            },
            "stations": result_stations
        }
        
    except Exception as e:
        print(f"🚨 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"API 호출 실패: {str(e)}")