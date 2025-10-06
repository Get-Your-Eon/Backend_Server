# FastAPI 엔드포인트 정의
#
# 프론트엔드 요청을 받고 서비스 레이어 호출 → JSON 응답 반환
from fastapi import APIRouter, Query
from app.schemas.station import StationListResponse, ChargerListResponse
from app.services.station_service import get_stations, get_chargers

router = APIRouter()

@router.get("/stations", response_model=StationListResponse)
async def stations(lat: float = Query(...), lng: float = Query(...)):
    data = await get_stations(lat, lng)
    return {"stations": data}

@router.get("/station/{station_id}/chargers", response_model=ChargerListResponse)
async def station_chargers(station_id: int):
    data = await get_chargers(station_id)
    return {"chargers": data}
