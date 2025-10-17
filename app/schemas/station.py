from pydantic import BaseModel, Field, conint
from typing import List, Optional


class ChargerBasic(BaseModel):
    id: str
    connector_types: List[str]
    # max power in kilowatts
    max_power_kw: Optional[float] = None
    status: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    # additional fields observed in external API
    bid: Optional[str] = None
    cpId: Optional[str] = None
    charger_code: Optional[str] = None  # csId
    cs_cat_code: Optional[str] = None
    info_coll_date: Optional[str] = None
    status_code: Optional[int] = None
    ch_start_date: Optional[str] = None
    last_ch_start_date: Optional[str] = None
    last_ch_end_date: Optional[str] = None
    updated_at: Optional[str] = None
    raw: Optional[dict] = None


class StationSummary(BaseModel):
    id: str
    name: str
    address: Optional[str]
    lat: float
    lon: float
    distance_m: Optional[int] = None
    charger_count: Optional[int] = None


class StationDetail(StationSummary):
    extra_info: Optional[dict] = None
    chargers: Optional[List[ChargerBasic]] = []


class StationListResponse(BaseModel):
    data: List[StationSummary]


class ChargerDetail(BaseModel):
    id: str
    station_id: Optional[str]
    connector_types: List[str]
    # max power in kilowatts
    max_power_kw: Optional[float] = None
    status: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    # additional raw fields
    bid: Optional[str] = None
    cpId: Optional[str] = None
    charger_code: Optional[str] = None
    cs_cat_code: Optional[str] = None
    info_coll_date: Optional[str] = None
    status_code: Optional[int] = None
    ch_start_date: Optional[str] = None
    last_ch_start_date: Optional[str] = None
    last_ch_end_date: Optional[str] = None
    updated_at: Optional[str] = None
    raw: Optional[dict] = None
# app/schemas/station.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# -----------------------------------
# 1. 충전소 단일 객체 응답용 모델
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
# 2. 충전소 리스트 응답 Wrapper
# -----------------------------------
class StationListResponse(BaseModel):
    stations: List[StationPublic]

# -----------------------------------
# 3. 충전기 상태 단일 객체 모델
# -----------------------------------
class ChargerBase(BaseModel):
    charger_id: int
    charger_type: Optional[str]
    output_kw: Optional[float]
    connector_type: Optional[str]
    status_code: Optional[int]

# -----------------------------------
# 4. 충전기 상태 업데이트 요청 모델
# -----------------------------------
class ChargerStatusUpdate(BaseModel):
    new_status_code: int

# -----------------------------------
# 5. 충전기 리스트 응답 Wrapper
# -----------------------------------
class ChargerListResponse(BaseModel):
    chargers: List[ChargerBase]
