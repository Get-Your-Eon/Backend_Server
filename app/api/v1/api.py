from fastapi import APIRouter
from app.api.v1 import auth # auth 라우터 import
from app.api.v1.station_router import router as station_router
from app.api.v1.station_router_kepco import router as kepco_station_router

api_router = APIRouter()

# v1 API 라우터에 auth 라우터 연결
api_router.include_router(auth.router)
# station router 연결 (기존 legacy API)
api_router.include_router(station_router)
# KEPCO station router 연결 (새로운 KEPCO API)
api_router.include_router(kepco_station_router)
# 다른 라우터들은 여기에 추가될 예정입니다.
