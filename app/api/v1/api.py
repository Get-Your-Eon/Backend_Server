from fastapi import APIRouter
from app.api.v1 import auth # auth 라우터 import
from app.api.v1.station_router_simple import router as station_router

api_router = APIRouter()

# v1 API 라우터에 auth 라우터 연결
api_router.include_router(auth.router)
# Simple station router - isolated from subsidy functionality
api_router.include_router(station_router)
# 다른 라우터들은 여기에 추가될 예정입니다.
