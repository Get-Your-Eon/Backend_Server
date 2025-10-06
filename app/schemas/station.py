# app/schemas/station.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# -----------------------------------
# 충전소 응답용 모델
# -----------------------------------
class StationPublic(BaseModel):
    id: int  # DB PK
    station_code: str
    name: str
    address: Optional[str]
    provider: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

# -----------------------------------
# 충전기 상태 모델
# -----------------------------------
class ChargerBase(BaseModel):
    charger_id: int
    charger_type: Optional[str]
    output_kw: Optional[float]
    connector_type: Optional[str]
    status_code: Optional[int]

# -----------------------------------
# 충전기 상태 업데이트 요청 모델
# -----------------------------------
class ChargerStatusUpdate(BaseModel):
    new_status_code: int
