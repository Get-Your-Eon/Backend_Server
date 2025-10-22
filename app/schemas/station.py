"""Pydantic schemas for Station API"""

from typing import List, Optional
from pydantic import BaseModel, Field


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