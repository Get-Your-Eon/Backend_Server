# app/schemas/__init__.py
from .station import (
    StationPublic,
    StationListResponse,       # ✅ 추가
    ChargerBase,
    ChargerStatusUpdate,
    ChargerListResponse        # ✅ 추가
)
from .subsidy import (
    SubsidyRequest,
    SubsidyPublic,
    SubsidyListResponse
)