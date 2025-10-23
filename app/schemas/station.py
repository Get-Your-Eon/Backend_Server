"""Pydantic schemas for Station API"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ChargerBase(BaseModel):
    """충전기 기본 정보 스키마."""
    charger_code: Optional[str] = Field(None, description="충전기 고유 코드")
    charger_type: Optional[str] = Field(None, description="충전 방식 (예: DC차데모, AC완속)")
    output_kw: Optional[float] = Field(None, description="충전기 출력 (kW)")
    connector_type: Optional[str] = Field(None, description="커넥터 타입")
    status_code: Optional[int] = Field(None, description="충전기 상태 코드 (0: 사용가능, 1: 충전중 등)")


class StationPublic(BaseModel):
    """공개 API용 충전소 정보 스키마 (충전기 목록 포함)."""
    id: int
    station_code: str = Field(..., description="충전소 고유 코드")
    name: str = Field(..., description="충전소 이름")
    address: Optional[str] = Field(None, description="주소")
    provider: Optional[str] = Field(None, description="충전소 제공 사업자")
    latitude: Optional[float] = Field(None, description="위도 (WGS 84)")
    longitude: Optional[float] = Field(None, description="경도 (WGS 84)")

    chargers: List[ChargerBase] = Field(default_factory=list, description="충전소에 속한 충전기 목록")

    class Config:
        # SQLAlchemy ORM 모델의 필드 이름을 Pydantic 모델의 필드 이름으로 자동 매핑합니다.
        from_attributes = True


class StationListResponse(BaseModel):
    """충전소 목록 응답 스키마."""
    stations: List[StationPublic] = Field(..., description="충전소 목록")
    total_count: int = Field(..., description="전체 충전소 수")


class ChargerStatusUpdate(BaseModel):
    """충전기 상태 업데이트 요청 스키마 (프로토콜 3번을 위한 입력 스키마)."""
    new_status_code: int = Field(..., description="업데이트할 새로운 충전기 상태 코드")


class ChargerListResponse(BaseModel):
    """충전기 목록 응답 스키마."""
    chargers: List[ChargerBase] = Field(..., description="충전기 목록")
    total_count: int = Field(..., description="전체 충전기 수")


class StationSearchRequest(BaseModel):
    """Request schema for station search by location"""
    lat: float = Field(..., description="User latitude", ge=-90, le=90)
    lon: float = Field(..., description="User longitude", ge=-180, le=180)
    radius: int = Field(1000, description="Search radius in meters", ge=100, le=10000)


class StationSummary(BaseModel):
    """Station summary for map display"""
    cs_id: str = Field(..., description="KEPCO station ID")
    addr: str = Field(..., description="Station address")
    cs_nm: str = Field(..., description="Station name")
    lat: str = Field(..., description="Latitude as string")
    longi: str = Field(..., description="Longitude as string")


class ChargerDetail(BaseModel):
    """Detailed charger information"""
    cp_id: str = Field(..., description="KEPCO charger ID")
    cp_nm: str = Field(..., description="Charger name")
    charge_tp: Optional[str] = Field(None, description="Charge type: 1=완속, 2=급속")
    cp_tp: Optional[str] = Field(None, description="Connector type code")
    cp_stat: Optional[str] = Field(None, description="Status code: 1=충전가능, 2=충전중, 3=고장/점검, 4=통신장애, 5=통신미연결")
    charge_method: Optional[str] = Field(None, description="Human readable charging method")
    status_text: str = Field(..., description="Human readable status")


class StationDetail(BaseModel):
    """Detailed station information with chargers"""
    cs_nm: str = Field(..., description="Station name")
    available_methods: str = Field(..., description="Available charging methods")
    chargers: List[ChargerDetail] = Field(..., description="List of chargers at this station")


class ChargerRequest(BaseModel):
    """Request schema for charger details"""
    cs_id: str = Field(..., description="KEPCO station ID")
    addr: str = Field(..., description="Station address")


class ErrorResponse(BaseModel):
    """Error response schema"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Error details")