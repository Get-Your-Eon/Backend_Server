from fastapi import APIRouter
from app.api.v1 import auth # auth 라우터 import
from app.api.v1.station_router import router as station_router
from app.api.v1.admin import router as admin_router
from app.api.v1.admin_db import router as admin_db_router

api_router = APIRouter()

# v1 API 라우터에 auth 라우터 연결
api_router.include_router(auth.router)
# station router 연결
api_router.include_router(station_router)
# admin router
api_router.include_router(admin_router)
api_router.include_router(admin_db_router, prefix="/admin")
# 다른 라우터들은 여기에 추가될 예정입니다.
