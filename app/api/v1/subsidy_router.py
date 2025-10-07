from typing import List

from fastapi import APIRouter, Depends, HTTPException
from starlette import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ----------------------------------------------------------------
# ✅ 프로젝트 내부 모듈의 절대 경로 임포트 (명확한 경로)
# ----------------------------------------------------------------
from app.database import get_async_session       # DB 세션 임포트
from app.models import Subsidy                   # Subsidy 모델 임포트
from app.schemas import SubsidyPublic            # ✅ __init__.py를 통한 명시적 노출된 클래스 임포트

# ----------------------------------------------------------------
# APIRouter 인스턴스 생성
# ----------------------------------------------------------------
router = APIRouter(
    prefix="/subsidies",
    tags=["Subsidies"]
)

# ----------------------------------------------------------------
# Subsidy Service (데이터베이스 로직)
# ----------------------------------------------------------------
class SubsidyService:
    """
    보조금 데이터에 대한 DB 상호작용 로직을 처리하는 서비스 클래스입니다.
    """

    @staticmethod
    async def get_subsidies_by_manufacturer_and_group(
            db: AsyncSession,
            manufacturer: str,
            model_group: str
    ) -> List[Subsidy]:
        """
        제조사(manufacturer)와 모델 그룹명(model_group)을 기준으로
        해당 그룹에 속하는 모든 상세 보조금 정보를 조회합니다.
        """

        normalized_model_group = model_group.upper()

        query = select(Subsidy).where(
            Subsidy.manufacturer == manufacturer,
            Subsidy.model_group == normalized_model_group
        ).order_by(Subsidy.model_name)

        result = await db.execute(query)
        return result.scalars().all()

# ----------------------------------------------------------------
# Subsidy Endpoints (FastAPI 라우터)
# ----------------------------------------------------------------
@router.get(
    "/search",
    response_model=List[SubsidyPublic],
    summary="제조사 및 모델 그룹별 보조금 정보 조회",
    description="특정 제조사의 특정 모델 그룹에 대한 모든 보조금 상세 정보를 조회합니다. (예: '현대', 'IONIQ5')"
)
async def search_subsidies(
        manufacturer: str,
        model_group: str,
        db: AsyncSession = Depends(get_async_session)
):
    """
    제조사(manufacturer)와 모델 그룹명(model_group)을 기준으로 보조금 정보를 검색합니다.
    """

    subsidies = await SubsidyService.get_subsidies_by_manufacturer_and_group(
        db=db,
        manufacturer=manufacturer,
        model_group=model_group
    )

    if not subsidies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"제조사 '{manufacturer}', 모델 그룹 '{model_group}'에 대한 보조금 정보를 찾을 수 없습니다."
        )

    return subsidies
