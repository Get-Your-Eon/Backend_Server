@app.get("/api/v1/stations", tags=["Station"], summary="🚀 KEPCO 2025 API - BRAND NEW")
async def kepco_2025_completely_new_implementation(
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
    🚀 KEPCO 2025 API - 완전히 새로운 구현
    이전 URL: /ws/chargePoint/curChargePoint (삭제됨)
    새 URL: /EVchargeManage.do (정확함)
    """
    print(f"🚀🚀🚀 KEPCO 2025 COMPLETELY NEW CODE 🚀🚀🚀")
    print(f"🚀 Function: kepco_2025_completely_new_implementation")
    print(f"🚀 Time: {datetime.now()}")
    print(f"🚀 Params: lat={lat}, lon={lon}, radius={radius}")
    
    try:
        # 좌표 → 주소 변환
        async def coords_to_addr(lat: float, lon: float) -> str:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://nominatim.openstreetmap.org/reverse",
                        params={"format": "json", "lat": lat, "lon": lon, "addressdetails": 1},
                        headers={"User-Agent": "KEPCO-2025-NEW"},
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        data = response.json()
                        addr_dict = data.get("address", {})
                        parts = []
                        if addr_dict.get("country") == "대한민국":
                            for key in ["city", "borough", "suburb"]:
                                if addr_dict.get(key):
                                    parts.append(addr_dict[key])
                        return " ".join(parts) if parts else f"{lat},{lon}"
                    return f"{lat},{lon}"
            except:
                return f"{lat},{lon}"
        
        # 거리 계산
        def calc_distance(lat1, lon1, lat2, lon2):
            try:
                R = 6371000
                lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
                dlat, dlon = lat2 - lat1, lon2 - lon1
                a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
                return R * 2 * math.asin(math.sqrt(a))
            except:
                return 999999
        
        # 1. 주소 변환
        search_addr = await coords_to_addr(lat, lon)
        print(f"🚀 검색주소: {search_addr}")
        
        # 2. KEPCO API 설정 확인
        from app.core.config import settings
        kepco_url = settings.EXTERNAL_STATION_API_BASE_URL
        kepco_key = settings.EXTERNAL_STATION_API_KEY
        
        print(f"🚀 KEPCO URL: {kepco_url}")
        print(f"🚀 올바른지 확인: https://bigdata.kepco.co.kr/openapi/v1/EVchargeManage.do")
        
        if not kepco_url or not kepco_key:
            raise HTTPException(status_code=500, detail="KEPCO 설정 누락")
        
        # 3. KEPCO API 호출
        async with httpx.AsyncClient() as client:
            kepco_response = await client.get(
                kepco_url,
                params={
                    "addr": search_addr,
                    "apiKey": kepco_key,
                    "returnType": "json"
                },
                timeout=30.0
            )
            
            print(f"🚀 KEPCO 응답: {kepco_response.status_code}")
            
            if kepco_response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"KEPCO API 실패: {kepco_response.status_code}"
                )
            
            kepco_data = kepco_response.json()
        
        # 4. 데이터 처리
        stations = []
        if isinstance(kepco_data, dict) and "data" in kepco_data:
            for item in kepco_data["data"]:
                try:
                    slat = float(item.get("lat", 0))
                    slon = float(item.get("longi", 0))
                    if slat == 0 or slon == 0:
                        continue
                    
                    dist = calc_distance(lat, lon, slat, slon)
                    if dist > radius:
                        continue
                    
                    stations.append({
                        "station_id": item.get("csId", ""),
                        "station_name": item.get("csNm", ""),
                        "address": item.get("addr", ""),
                        "lat": slat,
                        "lon": slon,
                        "distance_m": int(dist),
                        "charger_id": item.get("cpId", ""),
                        "charger_name": item.get("cpNm", ""),
                        "status": item.get("cpStat", ""),
                        "type": item.get("chargeTp", "")
                    })
                except:
                    continue
        
        # 5. 결과 반환
        stations.sort(key=lambda x: x["distance_m"])
        result = stations[:limit]
        
        return {
            "message": "🚀 KEPCO 2025 NEW SUCCESS",
            "status": "kepco_2025_new",
            "timestamp": datetime.now().isoformat(),
            "params": {"lat": lat, "lon": lon, "radius": radius, "addr": search_addr},
            "info": {"found": len(stations), "returned": len(result)},
            "stations": result
        }
    except Exception as e:
        print(f"🚨 KEPCO 2025 ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"KEPCO 검색 실패: {str(e)}")