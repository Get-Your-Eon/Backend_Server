from datetime import datetime
from pydantic import BaseModel
from typing import Optional

# 충전기 기본 정보
class ChargerBase(BaseModel):
    charger_code: str
    status_code: int
    updated_at: datetime
    charger_type: Optional[str]
    output_kw: Optional[float]

# 충전기 상태 업데이트 요청
class ChargerStatusUpdate(BaseModel):
    new_status_code: int
