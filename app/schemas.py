from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime

# PostGIS Geometry 타입을 위한 커스텀 임포트 (GeoAlchemy2와의 호환성)
# Pydantic 모델에서는 좌표값을 직접 Float 두 개로 받습니다.

# ----------------------------------------------------------------------
# 1. Output Schemas (API 응답 데이터 구조)
# ----------------------------------------------------------------------

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

# ----------------------------------------------------------------------
# 2. API Log Schemas (API 로그 기록용)
# ----------------------------------------------------------------------

class ApiLogBase(BaseModel):
    """API 로그 기록 기본 스키마."""
    endpoint: str = Field(..., description="요청 엔드포인트 경로")
    method: str = Field(..., description="HTTP 메서드 (GET, POST 등)")
    api_type: str = Field(..., description="API 타입 (예: StationInfo, StatusUpdate)")
    status_code: int = Field(..., description="HTTP 응답 상태 코드")
    response_code: Optional[int] = Field(None, description="외부 API 응답 코드")
    response_msg: Optional[str] = Field(None, description="외부 API 응답 메시지")
    response_time_ms: float = Field(..., description="응답 시간 (밀리초)")

    class Config:
        from_attributes = True

# ----------------------------------------------------------------------
# 3. Input Schemas (클라이언트로부터 데이터 업데이트 요청 시 사용)
# ----------------------------------------------------------------------

class ChargerStatusUpdate(BaseModel):
    """충전기 상태 업데이트 요청 스키마 (프로토콜 3번을 위한 입력 스키마)."""
    new_status_code: int = Field(..., description="업데이트할 새로운 충전기 상태 코드")
    # 선택적으로 상태 변경 사유 등을 추가할 수 있습니다.