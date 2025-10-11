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
    description="특정 제조사의 특정 모델 그룹에 대한 모든 보조금 상세 정보를 문자열 리스트로 조회합니다. "
                "(예: '현대자동차,GV60' → ['GV60 스탠다드 2WD 19인치,287,148,435', ...])"
)
async def search_subsidies(
        query: str = Query(..., description="제조사와 모델 그룹을 콤마로 구분 (예: '현대자동차,GV60')"),
        db: AsyncSession = Depends(get_async_session)
):
    """
    '현대자동차,GV60' 형태의 문자열을 파싱하여 DB 조회 후
    문자열 리스트 형태로 반환
    """

    # 문자열 파싱
    try:
        manufacturer, model_group = [x.strip() for x in query.split(",", 1)]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파라미터 형식이 올바르지 않습니다. 예: '현대자동차,GV60'"
        )

    # Service 호출
    subsidies = await subsidy_service.get_subsidy_info(
        db=db,
        manufacturer=manufacturer,
        model_group=model_group
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
