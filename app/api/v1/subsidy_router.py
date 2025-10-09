# app/api/v1/subsidy_router.py

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession

# ----------------------------------------------------------------
# 프로젝트 내부 모듈 import
# ----------------------------------------------------------------
from app.db.database import get_async_session
from app.schemas.subsidy import SubsidyPublic, SubsidyListResponse
from app.services.subsidy_service import subsidy_service

# ----------------------------------------------------------------
# APIRouter 인스턴스 생성
# ----------------------------------------------------------------
router = APIRouter(
    prefix="/subsidies",
    tags=["Subsidies"]
)

# ----------------------------------------------------------------
# Subsidy Endpoints
# ----------------------------------------------------------------
@router.get(
    "/search",
    response_model=SubsidyListResponse,
    summary="제조사 및 모델 그룹별 보조금 정보 조회",
    description="특정 제조사의 특정 모델 그룹에 대한 모든 보조금 상세 정보를 조회합니다. (예: '현대자동차', 'GV60')"
)
async def search_subsidies(
        manufacturer: str,
        model_group: str,
        db: AsyncSession = Depends(get_async_session)
):
    """
    제조사(manufacturer)와 모델 그룹명(model_group)을 기준으로 보조금 정보를 검색합니다.
    """

    # Service 호출
    subsidies = await subsidy_service.get_subsidy_info(
        db=db,
        manufacturer=manufacturer.strip(),
        model_group=model_group.strip()
    )

    if not subsidies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"제조사 '{manufacturer}', 모델 그룹 '{model_group}'에 대한 보조금 정보를 찾을 수 없습니다."
        )

    # SubsidyListResponse 형태로 반환
    return SubsidyListResponse(data=subsidies)
