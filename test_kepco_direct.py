#!/usr/bin/env python3
"""
KEPCO API 직접 테스트 스크립트
- 로컬에서 KEPCO API 응답을 확인
- Render 배포 버전과 비교하기 위함
"""

import httpx
import asyncio
import json
from typing import Dict, Any

# KEPCO API 설정
KEPCO_BASE_URL = "https://bigdata.kepco.co.kr/openapi/v1/EVchargeManage.do"
KEPCO_API_KEY = "***REMOVED***"

# 테스트 좌표 (강남역 근처)
TEST_LAT = 37.374109692
TEST_LON = 127.130205155

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 간의 거리 계산 (미터)"""
    import math
    
    # 지구 반지름 (km)
    R = 6371.0
    
    # 좌표를 라디안으로 변환
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # 차이 계산
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Haversine 공식
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    distance = R * c * 1000  # 미터로 변환
    return distance

async def get_address_from_coordinates(lat: float, lon: float) -> str:
    """좌표를 주소로 변환 (Nominatim 사용)"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "format": "json",
                    "lat": lat,
                    "lon": lon,
                    "addressdetails": 1
                },
                headers={"User-Agent": "EV-Charger-API/1.0"},
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                address_parts = []
                
                addr_dict = data.get("address", {})
                
                # 한국 주소 형식으로 구성
                if addr_dict.get("country") == "대한민국":
                    # 시/도
                    if "state" in addr_dict:
                        address_parts.append(addr_dict["state"])
                    
                    # 시/군/구
                    if "city" in addr_dict:
                        address_parts.append(addr_dict["city"])
                    elif "county" in addr_dict:
                        address_parts.append(addr_dict["county"])
                    
                    # 구/군
                    if "borough" in addr_dict:
                        address_parts.append(addr_dict["borough"])
                    
                    # 동/면/읍
                    if "suburb" in addr_dict:
                        address_parts.append(addr_dict["suburb"])
                    elif "village" in addr_dict:
                        address_parts.append(addr_dict["village"])
                    elif "town" in addr_dict:
                        address_parts.append(addr_dict["town"])
                
                return " ".join(address_parts) if address_parts else data.get("display_name", "")
            
            return f"{lat},{lon}"
    except Exception as e:
        print(f"⚠️ 주소 변환 실패: {e}")
        return f"{lat},{lon}"

async def test_kepco_api():
    """KEPCO API 직접 테스트"""
    print("🧪 KEPCO API 직접 테스트 시작")
    print(f"📍 테스트 좌표: {TEST_LAT}, {TEST_LON}")
    
    # 1. 좌표를 주소로 변환
    search_addr = await get_address_from_coordinates(TEST_LAT, TEST_LON)
    print(f"🗺️ 변환된 주소: {search_addr}")
    
    # 2. KEPCO API 호출
    try:
        async with httpx.AsyncClient() as client:
            print(f"🔗 KEPCO API 호출: {KEPCO_BASE_URL}")
            print(f"📋 파라미터:")
            print(f"   - addr: {search_addr}")
            print(f"   - apiKey: {KEPCO_API_KEY[:10]}...")
            print(f"   - returnType: json")
            
            response = await client.get(
                KEPCO_BASE_URL,
                params={
                    "addr": search_addr,
                    "apiKey": KEPCO_API_KEY,
                    "returnType": "json"
                },
                timeout=30.0
            )
            
            print(f"📡 응답 상태 코드: {response.status_code}")
            print(f"📄 응답 헤더: {dict(response.headers)}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"✅ JSON 파싱 성공")
                    print(f"📊 응답 데이터 구조:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                    
                    # 데이터 분석
                    if isinstance(data, list) and len(data) > 0:
                        print(f"\n📈 데이터 분석:")
                        print(f"   총 {len(data)}개 충전소 발견")
                        
                        for i, item in enumerate(data[:3]):  # 처음 3개만 분석
                            print(f"\n   충전소 {i+1}:")
                            for key, value in item.items():
                                print(f"     {key}: {value}")
                                
                            # 거리 계산
                            if "lat" in item and "longi" in item:
                                try:
                                    station_lat = float(item["lat"])
                                    station_lon = float(item["longi"])
                                    distance = calculate_distance(TEST_LAT, TEST_LON, station_lat, station_lon)
                                    print(f"     계산된 거리: {distance:.1f}m")
                                except:
                                    print(f"     거리 계산 실패")
                    else:
                        print(f"⚠️ 예상과 다른 응답 구조: {type(data)}")
                        
                except json.JSONDecodeError as e:
                    print(f"❌ JSON 파싱 실패: {e}")
                    print(f"📄 원본 응답 텍스트:")
                    print(response.text[:1000])
                    
            else:
                print(f"❌ API 호출 실패")
                print(f"📄 응답 내용:")
                print(response.text[:1000])
                
    except Exception as e:
        print(f"💥 KEPCO API 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_kepco_api())