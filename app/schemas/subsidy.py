# app/schemas/subsidy.py (values stored in 10k KRW units where applicable)

from pydantic import BaseModel, Field, conint
from typing import List, Optional

# --- 1. Request schema (input) ---
class SubsidyRequest(BaseModel):
    manufacturer: str = Field(..., description="자동차 제조사 이름 (필수)")
    model_group: str = Field(..., description="차량 모델 그룹 이름 (필수, 예: GV60)")

# --- 2. Response schema (output) ---
class SubsidyPublic(BaseModel):
    model_name: str = Field(..., description="세부 모델 이름 (풀 스펙)")

    # Note: subsidy fields are expressed in units of 10,000 KRW (10k KRW)
    subsidy_national_10k_won: conint(ge=0) = Field(..., description="국고 보조금 (단위: 만 원)")
    subsidy_local_10k_won: conint(ge=0) = Field(..., description="지자체 보조금 (단위: 만 원)")
    subsidy_total_10k_won: conint(ge=0) = Field(..., description="총 보조금 (단위: 만 원)")
    # 판매가(원) - DB에서는 NULL 허용
    sale_price: Optional[int] = Field(None, description="판매가(원)")

    class Config:
        from_attributes = True  # ORM 객체를 직렬화할 때 사용

# --- 3. List response wrapper ---
class SubsidyListResponse(BaseModel):
    data: List[SubsidyPublic]

# NOTE: Consolidate on `SubsidyPublic` / `SubsidyListResponse` instead of
# older `SubsidyResponse` types used previously.
