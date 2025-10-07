# app/schemas/subsidy.py (만원 단위 반영)

from pydantic import BaseModel, Field, conint
from typing import List

# --- 1. 요청 스키마 (Input) ---
class SubsidyRequest(BaseModel):
    manufacturer: str = Field(..., description="자동차 제조사 이름 (필수)")
    model_group: str = Field(..., description="차량 모델 그룹 이름 (필수, 예: GV60)")

# --- 2. 응답 스키마 (Output) ---
class SubsidyPublic(BaseModel):
    model_name: str = Field(..., description="세부 모델 이름 (풀 스펙)")

    # 만원 단위임을 필드명에 명시
    subsidy_national_10k_won: conint(ge=0) = Field(..., description="국고 보조금 (단위: 만 원)")
    subsidy_local_10k_won: conint(ge=0) = Field(..., description="지자체 보조금 (단위: 만 원)")
    subsidy_total_10k_won: conint(ge=0) = Field(..., description="총 보조금 (단위: 만 원)")

    class Config:
        from_attributes = True  # ORM 객체를 직렬화할 때 사용

# --- 3. 리스트 응답 스키마 (Output Wrapper) ---
class SubsidyListResponse(BaseModel):
    data: List[SubsidyPublic]
