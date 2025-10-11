# app/api/v1/subsidy_router.py

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_async_session
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
    response_model=list[str],
    summary="제조사 및 모델 그룹별 보조금 정보 조회",
    description="제조사와 모델 그룹을 각각 입력받아 해당 그룹의 상세 보조금 정보를 문자열 리스트로 조회합니다. "
                "(예: manufacturer='현대자동차', model_group='GV60' → ['GV60 스탠다드 2WD 19인치,287,148,435', ...])"
)
async def search_subsidies(
        manufacturer: str = Query(..., description="자동차 제조사 이름, 예: '현대자동차'"),
        model_group: str = Query(..., description="차량 모델 그룹 이름, 예: 'GV60'"),
        db: AsyncSession = Depends(get_async_session)
):
    """
    제조사(manufacturer)와 모델 그룹명(model_group)을 기준으로
    해당 그룹에 속하는 모든 상세 보조금 정보를 문자열 리스트로 반환합니다.
    포맷: "모델명,국고보조금,지자체보조금,총보조금"
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

    # 문자열 리스트로 변환: "모델명,국고,지자체,총액"
    result_list = [
        f"{s.model_name},{s.subsidy_national_10k_won},{s.subsidy_local_10k_won},{s.subsidy_total_10k_won}"
        for s in subsidies
    ]

    return result_list
